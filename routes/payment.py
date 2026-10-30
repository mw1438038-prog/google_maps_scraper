import hashlib
import hmac
from datetime import datetime, timezone

import requests
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models.freemius_webhook_event import FreemiusWebhookEvent
from models.user import User
from services.plan_limits import PLAN_LIMITS, PLAN_RANK


payment_bp = Blueprint("payment", __name__)

FREEMIUS_API_BASE = "https://api.freemius.com/v1"


# =====================================================
# HELPERS
# =====================================================

def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_datetime(value):
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(
            value,
            tz=timezone.utc,
        ).replace(tzinfo=None)

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(
                    timezone.utc
                ).replace(tzinfo=None)

            return parsed

        except ValueError:
            return None

    return None


def _unwrap(data, key):
    if isinstance(data, dict) and isinstance(data.get(key), dict):
        return data[key]

    return data


def _freemius_get(path):
    product_id = str(
        current_app.config.get("FREEMIUS_PRODUCT_ID") or ""
    ).strip()

    token = str(
        current_app.config.get("FREEMIUS_API_BEARER_TOKEN") or ""
    ).strip()

    if not product_id or not token:
        raise RuntimeError(
            "Freemius product ID or API bearer token is missing."
        )

    url = (
        f"{FREEMIUS_API_BASE}/products/"
        f"{product_id}/{path.lstrip('/')}"
    )

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def _verify_freemius_signature(raw_body, signature):
    secret = str(
        current_app.config.get("FREEMIUS_PRODUCT_SECRET_KEY") or ""
    ).strip()

    if not secret or not signature:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected,
        signature.strip(),
    )


def _get_event_license_id(event):
    objects = event.get("objects") or {}

    license_data = objects.get("license") or {}

    if isinstance(license_data, dict) and license_data.get("id"):
        return str(license_data["id"])

    subscription = objects.get("subscription") or {}

    if (
        isinstance(subscription, dict)
        and subscription.get("license_id")
    ):
        return str(subscription["license_id"])

    if (
        isinstance(subscription, dict)
        and isinstance(subscription.get("license"), dict)
        and subscription["license"].get("id")
    ):
        return str(subscription["license"]["id"])

    payment = objects.get("payment") or {}

    if isinstance(payment, dict):
        if payment.get("license_id"):
            return str(payment["license_id"])

        if (
            isinstance(payment.get("license"), dict)
            and payment["license"].get("id")
        ):
            return str(payment["license"]["id"])

    data = event.get("data") or {}

    if isinstance(data, dict):
        if data.get("license_id"):
            return str(data["license_id"])

        if (
            isinstance(data.get("license"), dict)
            and data["license"].get("id")
        ):
            return str(data["license"]["id"])

        if (
            isinstance(data.get("subscription"), dict)
            and data["subscription"].get("license_id")
        ):
            return str(data["subscription"]["license_id"])

    return None


def _get_local_user_for_license(license_data):
    user_id = license_data.get("user_id")

    if user_id is not None:
        try:
            freemius_user = _unwrap(
                _freemius_get(f"users/{user_id}.json"),
                "user",
            )

        except (
            requests.RequestException,
            ValueError,
            RuntimeError,
        ):
            current_app.logger.exception(
                "Could not retrieve Freemius user details."
            )
            freemius_user = None

        email = (
            freemius_user.get("email")
            if isinstance(freemius_user, dict)
            else None
        )

        if email:
            user = User.query.filter(
                func.lower(User.email) == email.strip().lower()
            ).first()

            if user:
                return user

    return User.query.filter_by(
        payment_provider="freemius",
        payment_reference=str(license_data.get("id", "")),
    ).first()


def _plan_from_license(license_data):
    plan_id = str(license_data.get("plan_id", "")).strip()

    pro_id = str(
        current_app.config.get("FREEMIUS_PRO_PLAN_ID") or ""
    ).strip()

    business_id = str(
        current_app.config.get("FREEMIUS_BUSINESS_PLAN_ID") or ""
    ).strip()

    if pro_id and plan_id == pro_id:
        return "pro"

    if business_id and plan_id == business_id:
        return "business"

    current_app.logger.warning(
        "Unrecognized Freemius plan ID: %s",
        plan_id or "(missing)",
    )

    return None


# =====================================================
# SYNC LATEST LICENSE STATE
# =====================================================

def _sync_license(license_id):
    license_data = _unwrap(
        _freemius_get(f"licenses/{license_id}.json"),
        "license",
    )

    if not isinstance(license_data, dict):
        raise ValueError(
            "Unexpected Freemius license response."
        )

    actual_license_id = license_data.get("id", license_id)

    user = _get_local_user_for_license(license_data)

    if not user:
        current_app.logger.warning(
            "No local account matched Freemius license %s.",
            actual_license_id,
        )
        return False

    plan = _plan_from_license(license_data)

    if not plan:
        current_app.logger.warning(
            "Cannot map Freemius license %s to a configured plan.",
            actual_license_id,
        )
        return False

    expires_at = _parse_datetime(
        license_data.get("expiration")
    )

    is_canceled = bool(
        license_data.get(
            "is_cancelled",
            license_data.get("is_canceled", False),
        )
    )

    now = _utc_now()

    old_expiry = user.subscription_expires_at

    if old_expiry and old_expiry.tzinfo is not None:
        old_expiry = old_expiry.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    old_license_id = (
        user.payment_reference
        if user.payment_provider == "freemius"
        else None
    )

    old_plan = (user.plan or "free").strip().lower()
    if old_plan not in PLAN_LIMITS:
        old_plan = "free"
    old_searches_used = max(int(user.searches_used or 0), 0)

    is_expired = (
        expires_at is not None
        and expires_at <= now
    )

    # Do not grant paid access to canceled or expired licenses.
    if is_canceled or is_expired:
        user.plan = "free"
        user.subscription_status = (
            "canceled" if is_canceled else "expired"
        )
        user.searches_limit = PLAN_LIMITS["free"]["searches"]
        user.searches_used = PLAN_LIMITS["free"]["searches"]
        user.searches_rollover_remaining = 0
        user.free_trial_used = True
        user.subscription_expires_at = expires_at
        user.payment_provider = "freemius"
        user.payment_reference = str(actual_license_id)

        current_app.logger.info(
            "Freemius license %s is canceled or expired.",
            actual_license_id,
        )

        return True

    # Expiration must be known before paid access is granted.
    if expires_at is None:
        current_app.logger.warning(
            "Freemius license %s has no valid expiration.",
            actual_license_id,
        )
        return False

    plan_changed = old_plan != plan
    new_subscription_period = (
        old_license_id != str(actual_license_id)
        or old_expiry is None
        or expires_at > old_expiry
    )

    if plan_changed:
        carryover_searches = 0
        if PLAN_RANK[plan] > PLAN_RANK[old_plan]:
            previous_base_quota = PLAN_LIMITS[old_plan]["searches"]
            free_was_already_claimed = (
                old_plan == "free" and bool(user.free_trial_used)
            )
            if not free_was_already_claimed:
                if old_plan == "free":
                    carryover_searches = max(
                        previous_base_quota - old_searches_used,
                        0,
                    )
                else:
                    old_rollover_total = max(
                        int(user.searches_limit or 0)
                        - previous_base_quota,
                        0,
                    )
                    old_rollover_remaining = min(
                        max(
                            int(user.searches_rollover_remaining or 0),
                            0,
                        ),
                        old_rollover_total,
                    )
                    old_rollover_used = (
                        old_rollover_total - old_rollover_remaining
                    )
                    previous_plan_used = max(
                        old_searches_used - old_rollover_used,
                        0,
                    )
                    carryover_searches = max(
                        previous_base_quota - previous_plan_used,
                        0,
                    )

        user.searches_used = 0
        user.searches_reset_at = now
        user.searches_rollover_remaining = carryover_searches
        user.searches_limit = (
            PLAN_LIMITS[plan]["searches"] + carryover_searches
        )
    elif new_subscription_period:
        # A successful renewal (or a genuinely new same-tier subscription)
        # starts with the normal allowance, dropping any prior rollover.
        user.searches_used = 0
        user.searches_reset_at = now
        user.searches_rollover_remaining = 0
        user.searches_limit = PLAN_LIMITS[plan]["searches"]

    user.plan = plan
    user.free_trial_used = True
    user.subscription_status = "active"
    user.subscription_expires_at = expires_at
    user.payment_provider = "freemius"
    user.payment_reference = str(actual_license_id)

    if (
        not user.subscription_started_at
        or old_plan != plan
    ):
        user.subscription_started_at = now

    current_app.logger.info(
        "Freemius license %s synchronized for local user %s.",
        actual_license_id,
        user.id,
    )

    return True


# =====================================================
# DOWNGRADE LOCAL USER
# =====================================================

def _downgrade_license(license_id):
    user = User.query.filter_by(
        payment_provider="freemius",
        payment_reference=str(license_id),
    ).first()

    if not user:
        current_app.logger.warning(
            "No local user found for deleted license %s.",
            license_id,
        )
        return True

    user.plan = "free"
    user.subscription_status = "expired"
    user.subscription_expires_at = _utc_now()
    user.searches_limit = PLAN_LIMITS["free"]["searches"]
    user.searches_used = PLAN_LIMITS["free"]["searches"]
    user.searches_rollover_remaining = 0
    user.free_trial_used = True

    current_app.logger.info(
        "Local user %s downgraded after license deletion.",
        user.id,
    )

    return True


# =====================================================
# FREEMIUS WEBHOOK
# =====================================================

@payment_bp.route(
    "/api/payment/webhook",
    methods=["POST"],
)
def freemius_webhook():
    raw_body = request.get_data(cache=True)
    signature = request.headers.get("x-signature", "")

    if not _verify_freemius_signature(raw_body, signature):
        current_app.logger.warning(
            "Rejected Freemius webhook: invalid signature."
        )

        return jsonify({
            "success": False,
            "message": "Invalid webhook signature.",
        }), 401

    try:
        event = request.get_json(silent=True)
        if not isinstance(event, dict):
            return jsonify({
                "success": False,
                "message": "Invalid webhook payload.",
            }), 400

        event_type = str(event.get("type", "unknown")).strip() or "unknown"
        license_id = _get_event_license_id(event)
        raw_event_id = str(event.get("id") or "").strip()
        event_id = (
            f"freemius:{raw_event_id}"
            if raw_event_id
            else f"payload:{hashlib.sha256(raw_body).hexdigest()}"
        )

        existing_event = db.session.get(
            FreemiusWebhookEvent,
            event_id,
        )
        if existing_event:
            current_app.logger.info(
                "Ignoring duplicate Freemius event %s (%s).",
                event_id,
                event_type,
            )
            return jsonify({
                "success": True,
                "message": "Duplicate event already processed.",
            }), 200

        event_record = FreemiusWebhookEvent(
            event_id=event_id,
            event_type=event_type,
        )
        db.session.add(event_record)
        try:
            # Claim the event ID before processing, within the same DB
            # transaction as the subscription/quota update.
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            if db.session.get(FreemiusWebhookEvent, event_id):
                return jsonify({
                    "success": True,
                    "message": "Duplicate event already processed.",
                }), 200
            raise

        current_app.logger.info(
            "Freemius webhook received: %s (event %s).",
            event_type,
            event_id,
        )

        license_events = {
            "payment.created",
            "license.created",
            "license.activated",
            "license.extended",
            "license.shortened",
            "license.updated",
            "license.cancelled",
            "license.expired",
            "license.plan.changed",
            "license.deleted",
            "subscription.cancelled",
            "subscription.renewal.failed.last",
        }

        if event_type in license_events:
            if not license_id:
                db.session.rollback()
                current_app.logger.error(
                    "Freemius event %s has no license ID.",
                    event_type,
                )
                return jsonify({
                    "success": False,
                    "message": "License ID missing from webhook.",
                }), 500

            if event_type == "license.deleted":
                _downgrade_license(license_id)
            else:
                synced = _sync_license(license_id)
                if not synced:
                    db.session.rollback()
                    return jsonify({
                        "success": False,
                        "message": "Could not synchronize license.",
                    }), 500

        else:
            current_app.logger.info(
                "Ignoring unrelated Freemius event: %s",
                event_type,
            )

        event_record.processed_at = _utc_now()
        db.session.commit()

        return jsonify({
            "success": True,
            "message": (
                "License synchronized."
                if event_type in license_events
                else "Event ignored."
            ),
        }), 200

    except requests.RequestException:
        db.session.rollback()

        current_app.logger.exception(
            "Freemius API request failed during webhook processing."
        )

        return jsonify({
            "success": False,
            "message": "Freemius API request failed.",
        }), 503

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Freemius webhook processing failed."
        )

        return jsonify({
            "success": False,
            "message": "Webhook processing failed.",
        }), 500
