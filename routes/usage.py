
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, session

from extensions import db
from models.user import User


usage_bp = Blueprint("usage", __name__)


# =====================================================
# PLAN LIMITS
# =====================================================

PLAN_LIMITS = {
    "free": {
        "searches": 10,
        "results_per_search": 15,
    },
    "pro": {
        "searches": 500,
        "results_per_search": 100,
        "duration_days": 30,
    },
    "business": {
        "searches": 1000,
        "results_per_search": 200,
        "duration_days": 30,
    },
}


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

    except Exception:
        db.session.rollback()
        session.clear()
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
        return True

    now = datetime.utcnow()

    if expires_at.tzinfo is not None:
        now = datetime.now(expires_at.tzinfo)

    if now >= expires_at:
        if (
            user.subscription_status != "expired"
            or (user.plan or "free").lower() != "free"
        ):
            user.subscription_status = "expired"
            user.plan = "free"
            user.searches_limit = PLAN_LIMITS["free"]["searches"]
            db.session.commit()

        return True

    return False


# =====================================================
# USAGE RESET
# =====================================================

def reset_usage_if_needed(user):
    if not user:
        return

    plan = get_user_plan(user)

    if plan == "free":
        return

    if check_subscription_expiry(user):
        return

    if (user.subscription_status or "").lower() != "active":
        return

    now = datetime.utcnow()
    reset_at = user.searches_reset_at

    if reset_at and reset_at.tzinfo is not None:
        now = datetime.now(reset_at.tzinfo)

    if not reset_at:
        user.searches_reset_at = now
        db.session.commit()
        return

    if now >= reset_at + timedelta(days=30):
        user.searches_used = 0
        user.searches_reset_at = now
        db.session.commit()


# =====================================================
# CAN SEARCH
# =====================================================

def can_search(user):
    if not user:
        return False

    if check_subscription_expiry(user):
        return False

    reset_usage_if_needed(user)

    if check_subscription_expiry(user):
        return False

    plan = get_user_plan(user)
    limits = get_plan_limits(user)

    if plan == "free":
        if user.free_trial_used:
            return False

        if user.searches_used >= limits["searches"]:
            user.free_trial_used = True
            db.session.commit()
            return False

        return True

    if (user.subscription_status or "").lower() != "active":
        return False

    if user.searches_used >= limits["searches"]:
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

    if not subscription_expired:
        reset_usage_if_needed(user)
        subscription_expired = check_subscription_expiry(user)

    plan = get_user_plan(user)
    limits = get_plan_limits(user)

    used = user.searches_used or 0
    limit = limits["searches"]
    remaining = max(limit - used, 0)

    if plan != "free" and (
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
        "free_trial_used": bool(user.free_trial_used),
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

    if not can_search(user):
        return False

    plan = get_user_plan(user)
    limits = get_plan_limits(user)

    if user.searches_used >= limits["searches"]:
        return False

    user.searches_used += 1

    if plan == "free" and user.searches_used >= limits["searches"]:
        user.free_trial_used = True

    if history_record is not None:
        db.session.add(history_record)

    db.session.commit()
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
