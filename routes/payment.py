
import hashlib
import hmac
from datetime import datetime, timezone

import requests

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models.user import User


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
            value, tz=timezone.utc
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

    if license_data.get("id"):
        return str(license_data["id"])

    subscription = objects.get("subscription") or {}
    if subscription.get("license_id"):
        return str(subscription["license_id"])

    data = event.get("data") or {}

    if data.get("license_id"):
        return str(data["license_id"])

    if isinstance(data.get("license"), dict):
        license_id = data["license"].get("id")
        if license_id:
            return str(license_id)

    return None


def _get_local_user_for_license(license_data):
    user_id = license_data.get("user_id")

    if user_id is not None:
        # The Freemius user ID is NOT our local database user ID.
        # Do not look up the local user by this ID.
        try:
            freemius_user = _unwrap(
                _freemius_get(f"users/{user_id}.json"),
                "user",
            )
        except (requests.RequestException, ValueError, RuntimeError):
            current_app.logger.exception(
                "Could not retrieve Freemius user details."
            )
            return None

        email = (
            freemius_user.get("email")
            if isinstance(freemius_user, dict)
            else None
        )

        if email:
            user = User.query.filter_by(
                email=email.strip().lower()
            ).first()

            if user:
                return user

    # Existing licenses previously saved to this local account.
    return User.query.filter_by(
        payment_provider="freemius",
        payment_reference=str(license_data.get("id", "")),
    ).first()


def _plan_from_license(license_data):
    plan_id = str(license_data.get("plan_id", ""))

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
        raise ValueError("Unexpected Freemius license response.")

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
            "Unknown Freemius plan ID on license %s.",
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

    old_plan = (user.plan or "free").lower()

    # Canceled or expired licenses must not grant paid access.
    is_expired = expires_at is not None and expires_at <= now

    if is_canceled or is_expired:
        user.subscription_status = (
            "canceled" if is_canceled else "expired"
        )
        user.plan = "free"
        user.searches_limit = 10
        user.subscription_expires_at = expires_at
        user.payment_provider = "freemius"
        user.payment_reference = str(actual_license_id)
        db.session.commit()
        return True

    if expires_at is None:
        current_app.logger.warning(
            "Freemius license %s has no expiration; "
            "paid access was not activated.",
            actual_license_id,
        )
        return False

    # Reset usage on first activation, license replacement,
    # plan change, or confirmed extension into a new period.
    new_billing_period = (
        old_license_id != str(actual_license_id)
        or old_plan != plan
        or old_expiry is None
        or expires_at > old_expiry
    )

    if new_billing_period:
        user.searches_used = 0
        user.searches_reset_at = now

    user.plan = plan
    user.searches_limit = (
        500 if plan == "pro" else 1000
    )
    user.subscription_status = "active"
    user.subscription_expires_at = expires_at
    user.payment_provider = "freemius"
    user.payment_reference = str(actual_license_id)

    if not user.subscription_started_at or old_plan != plan:
        user.subscription_started_at = now

    db.session.commit()

    current_app.logger.info(
        "Freemius license %s synchronized for local user %s.",
        actual_license_id,
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

        event_type = str(event.get("type", ""))
        license_id = _get_event_license_id(event)

        current_app.logger.info(
            "Freemius webhook received: %s",
            event_type,
        )

        license_events = {
            "license.created",
            "license.activated",
            "license.extended",
            "license.shortened",
            "license.updated",
            "license.cancelled",
            "license.expired",
            "license.plan.changed",
            "subscription.cancelled",
            "subscription.renewal.failed.last",
        }

        if event_type == "license.deleted":
            if not license_id:
                return jsonify({"success": True}), 200

            user = User.query.filter_by(
                payment_provider="freemius",
                payment_reference=str(license_id),
            ).first()

            if user:
                user.plan = "free"
                user.subscription_status = "expired"
                user.subscription_expires_at = _utc_now()
                user.searches_limit = 10
                db.session.commit()

        elif event_type in license_events:
            if not license_id:
                current_app.logger.warning(
                    "Freemius license event did not include a license ID."
                )
                return jsonify({"success": True}), 200

            synced = _sync_license(license_id)

            if not synced:
                # Ask Freemius to retry rather than silently
                # acknowledging an event that could not sync.
                return jsonify({
                    "success": False,
                    "message": "Could not synchronize license.",
                }), 500

        # Ignore unrelated events.
        return jsonify({"success": True}), 200

    except requests.RequestException:
        db.session.rollback()
        current_app.logger.exception(
            "Freemius API request failed during webhook processing."
        )
        return jsonify({"success": False}), 503

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Freemius webhook processing failed."
        )
        return jsonify({"success": False}), 500
