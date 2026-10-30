
from datetime import datetime

from flask import Blueprint, jsonify, session
from sqlalchemy import case, update

from extensions import db
from models.user import User
from services.plan_limits import PLAN_LIMITS


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
            user.searches_used = PLAN_LIMITS["free"]["searches"]
            user.searches_rollover_remaining = 0
            user.free_trial_used = True
            db.session.commit()

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

    used = user.searches_used or 0
    free_trial_used = bool(user.free_trial_used)

    if plan == "free":
        limit = limits["searches"]
        remaining = (
            0 if free_trial_used else max(limit - used, 0)
        )
    else:
        limit = max(
            int(user.searches_limit or 0),
            limits["searches"],
        )
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
    limits = get_plan_limits(user)

    if not can_search(user):
        return False

    quota_limit = (
        limits["searches"]
        if plan == "free"
        else max(
            int(user.searches_limit or 0),
            limits["searches"],
        )
    )
    conditions = [
        User.id == user.id,
        User.searches_used < quota_limit,
    ]

    if plan == "free":
        conditions.extend([
            User.plan == "free",
            User.free_trial_used.is_(False),
        ])
    else:
        conditions.extend([
            User.plan == plan,
            User.subscription_status == "active",
            User.subscription_expires_at > datetime.utcnow(),
            User.searches_used < User.searches_limit,
        ])

    statement = update(User).where(*conditions).values(
        searches_used=User.searches_used + 1,
    )
    if plan == "free":
        statement = statement.values(
            free_trial_used=case(
                (
                    User.searches_used + 1 >= limits["searches"],
                    True,
                ),
                else_=User.free_trial_used,
            ),
        )
    else:
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
