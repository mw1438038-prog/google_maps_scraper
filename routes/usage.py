
from datetime import datetime, timezone

from flask import Blueprint, jsonify, session
from sqlalchemy import case, update

from extensions import db
from models.user import User
from services.plan_limits import PLAN_LIMITS
from services.monitoring import record_error
from services.quotas import (
    expire_subscription_to_free,
    refresh_free_quota,
)


usage_bp = Blueprint("usage", __name__)


# =====================================================
# CURRENT USER
# =====================================================

def get_current_user():
    user_data = session.get("user")

    if not user_data:
        return None

    user_id = user_data.get("id")

    if not user_id:
        session.clear()
        return None

    try:
        user = db.session.get(User, user_id)

        if user is None:
            session.clear()
            return None

        return user

    except Exception as error:
        db.session.rollback()
        session.clear()
        record_error(
            "neon", "ERROR", "Database user lookup failed.",
            exception=error, status=503,
        )
        return None


# =====================================================
# USER PLAN
# =====================================================

def get_user_plan(user):
    if not user:
        return "free"

    plan = (user.plan or "free").lower().strip()

    if plan not in PLAN_LIMITS:
        return "free"

    return plan


def get_plan_limits(user):
    return PLAN_LIMITS[get_user_plan(user)]


# =====================================================
# SUBSCRIPTION EXPIRY
# =====================================================

def check_subscription_expiry(user):
    if not user:
        return False

    plan = get_user_plan(user)

    if plan == "free":
        return False

    expires_at = user.subscription_expires_at

    if not expires_at:
        expire_subscription_to_free(user)
        return True

    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)

    if now >= expires_at:
        if (
            user.subscription_status != "expired"
            or (user.plan or "free").lower() != "free"
        ):
            expire_subscription_to_free(user)

        return True

    return False


# =====================================================
# CAN SEARCH
# =====================================================

def can_search(user):
    if not user:
        return False

    if check_subscription_expiry(user):
        return False

    plan = get_user_plan(user)

    if plan == "free":
        refresh_free_quota(user)
        return user.searches_used < PLAN_LIMITS["free"]["searches"]

    if (user.subscription_status or "").lower() != "active":
        return False

    if plan == "business":
        return True

    limits = get_plan_limits(user)
    quota_limit = max(
        int(user.searches_limit or 0),
        limits["searches"],
    )

    if user.searches_used >= quota_limit:
        return False

    return True


# =====================================================
# GET USAGE
# =====================================================

def get_usage(user):
    if not user:
        return {
            "plan": "free",
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "results_per_search": 0,
            "free_trial_used": False,
            "subscription_status": "inactive",
            "subscription_expires_at": None,
            "subscription_expired": False,
        }

    subscription_expired = check_subscription_expiry(user)

    plan = get_user_plan(user)
    limits = get_plan_limits(user)
    if plan == "free":
        refresh_free_quota(user)

    used = user.searches_used or 0
    free_trial_used = bool(user.free_trial_used)

    if plan == "free":
        limit = limits["searches"]
        remaining = max(limit - used, 0)
    elif plan == "business":
        limit = None
        remaining = None
    else:
        limit = max(
            int(user.searches_limit or 0),
            limits["searches"],
        )
        remaining = max(limit - used, 0)

    if plan == "pro" and (
        subscription_expired
        or (user.subscription_status or "").lower() != "active"
    ):
        remaining = 0

    expires_at = user.subscription_expires_at

    return {
        "plan": plan,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "results_per_search": limits["results_per_search"],
        "free_trial_used": free_trial_used,
        "subscription_status": user.subscription_status or "inactive",
        "subscription_expires_at": (
            expires_at.isoformat() if expires_at else None
        ),
        "subscription_expired": subscription_expired,
    }


# =====================================================
# CONSUME SEARCH
# =====================================================

def consume_search(user, history_record=None):
    if not user:
        return False

    plan = get_user_plan(user)
    if not can_search(user):
        return False

    conditions = [User.id == user.id]

    if plan == "free":
        conditions.extend([
            User.plan == "free",
            User.searches_used < PLAN_LIMITS["free"]["searches"],
        ])
    elif plan == "business":
        conditions.extend([
            User.plan == "business",
            User.subscription_status == "active",
            User.subscription_expires_at > datetime.utcnow(),
        ])
    else:
        conditions.extend([
            User.plan == plan,
            User.subscription_status == "active",
            User.subscription_expires_at > datetime.utcnow(),
            User.searches_used < max(
                int(user.searches_limit or 0),
                PLAN_LIMITS[plan]["searches"],
            ),
        ])

    statement = update(User).where(*conditions).values(
        searches_used=User.searches_used + 1,
    )
    if plan == "free":
        statement = statement.values(
            free_trial_used=case(
                (
                    User.searches_used + 1
                    >= PLAN_LIMITS["free"]["searches"],
                    True,
                ),
                else_=User.free_trial_used,
            ),
        )
    elif plan == "pro":
        statement = statement.values(
            searches_rollover_remaining=case(
                (
                    User.searches_rollover_remaining > 0,
                    User.searches_rollover_remaining - 1,
                ),
                else_=User.searches_rollover_remaining,
            ),
        )

    result = db.session.execute(
        statement.execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False

    if history_record is not None:
        db.session.add(history_record)

    db.session.commit()
    db.session.refresh(user)
    return True


# =====================================================
# USAGE API
# =====================================================

@usage_bp.route("/api/usage", methods=["GET"])
def usage():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please login before viewing usage.",
        }), 401

    return jsonify({
        "success": True,
        "usage": get_usage(user),
    })
