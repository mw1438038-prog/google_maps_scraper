
from datetime import (
    datetime,
    timedelta,
)

from flask import (
    Blueprint,
    jsonify,
    session,
)

from extensions import db
from models.user import User


# =====================================================
# BLUEPRINT
# =====================================================

usage_bp = Blueprint(
    "usage",
    __name__,
)


# =====================================================
# PLAN LIMITS
# =====================================================

PLAN_LIMITS = {

    # ---------------------------------------------
    # FREE
    #
    # 10 searches lifetime
    # 15 results per search
    # ---------------------------------------------

    "free": {
        "searches": 10,
        "results_per_search": 15,
    },

    # ---------------------------------------------
    # PRO
    #
    # 100 searches per subscription period
    # 100 results per search
    # 30 days
    # ---------------------------------------------

    "pro": {
        "searches": 100,
        "results_per_search": 100,
        "duration_days": 30,
    },

    # ---------------------------------------------
    # BUSINESS
    #
    # 500 searches per subscription period
    # 200 results per search
    # 30 days
    # ---------------------------------------------

    "business": {
        "searches": 500,
        "results_per_search": 200,
        "duration_days": 30,
    },
}


# =====================================================
# CURRENT USER
# =====================================================

def get_current_user():

    user_data = session.get(
        "user"
    )

    if not user_data:
        return None

    user_id = user_data.get(
        "id"
    )

    if not user_id:
        return None

    return db.session.get(
        User,
        user_id
    )


# =====================================================
# GET USER PLAN
# =====================================================

def get_user_plan(user):

    if not user:
        return "free"

    plan = (
        user.plan or "free"
    ).lower().strip()

    if plan not in PLAN_LIMITS:

        plan = "free"

    return plan


# =====================================================
# GET PLAN LIMITS
# =====================================================

def get_plan_limits(user):

    plan = get_user_plan(
        user
    )

    return PLAN_LIMITS[
        plan
    ]


# =====================================================
# CHECK SUBSCRIPTION EXPIRY
#
# Applies to:
# - Pro
# - Business
#
# Free never expires.
#
# IMPORTANT:
# This does NOT reset a paid user back to Free.
#
# It marks the subscription as expired and blocks
# further searches until the user renews/upgrades.
# =====================================================

def check_subscription_expiry(user):

    if not user:
        return False

    plan = get_user_plan(
        user
    )

    # ---------------------------------------------
    # FREE HAS NO SUBSCRIPTION EXPIRY
    # ---------------------------------------------

    if plan == "free":

        return False

    # ---------------------------------------------
    # PAID PLAN MUST HAVE AN EXPIRY DATE
    # ---------------------------------------------

    expires_at = (
        user.subscription_expires_at
    )

    if not expires_at:

        return False

    now = datetime.utcnow()

    # ---------------------------------------------
    # SUBSCRIPTION EXPIRED
    # ---------------------------------------------

    if now >= expires_at:

        if (
            user.subscription_status
            != "expired"
        ):

            user.subscription_status = (
                "expired"
            )

            db.session.commit()

        return True

    # ---------------------------------------------
    # SUBSCRIPTION STILL ACTIVE
    # ---------------------------------------------

    return False


# =====================================================
# RESET PAID PLAN USAGE
#
# IMPORTANT:
#
# This function ONLY resets usage when a paid
# subscription is still active and its 30-day
# usage period has completed.
#
# If subscription itself has expired, usage is
# NOT reset.
# =====================================================

def reset_usage_if_needed(user):

    if not user:
        return

    plan = get_user_plan(
        user
    )

    # ---------------------------------------------
    # FREE NEVER RESETS
    # ---------------------------------------------

    if plan == "free":
        return

    # ---------------------------------------------
    # CHECK SUBSCRIPTION EXPIRY FIRST
    # ---------------------------------------------

    if check_subscription_expiry(
        user
    ):

        return

    now = datetime.utcnow()

    reset_at = (
        user.searches_reset_at
    )

    # ---------------------------------------------
    # FIRST PAID PERIOD
    # ---------------------------------------------

    if not reset_at:

        user.searches_used = 0

        user.searches_reset_at = now

        db.session.commit()

        return

    # ---------------------------------------------
    # 30 DAYS COMPLETED
    #
    # Only reset if subscription is still active.
    # ---------------------------------------------

    if now >= (
        reset_at
        + timedelta(days=30)
    ):

        user.searches_used = 0

        user.searches_reset_at = now

        db.session.commit()


# =====================================================
# CAN SEARCH
#
# IMPORTANT:
#
# This function runs BEFORE Google API.
#
# Therefore:
#
# - expired Pro users do NOT call Google API
# - expired Business users do NOT call Google API
# - exhausted Free users do NOT call Google API
# =====================================================

def can_search(user):

    if not user:

        return False

    # ---------------------------------------------
    # CHECK PAID SUBSCRIPTION EXPIRY
    # ---------------------------------------------

    if check_subscription_expiry(
        user
    ):

        return False

    # ---------------------------------------------
    # RESET USAGE IF REQUIRED
    # ---------------------------------------------

    reset_usage_if_needed(
        user
    )

    # ---------------------------------------------
    # CHECK AGAIN
    #
    # reset_usage_if_needed() may detect expiry.
    # ---------------------------------------------

    if check_subscription_expiry(
        user
    ):

        return False

    plan = get_user_plan(
        user
    )

    limits = get_plan_limits(
        user
    )

    # =================================================
    # FREE PLAN
    # =================================================

    if plan == "free":

        # ---------------------------------------------
        # FREE TRIAL ALREADY USED
        # ---------------------------------------------

        if user.free_trial_used:

            return False

        # ---------------------------------------------
        # SAFETY CHECK
        # ---------------------------------------------

        if (
            user.searches_used
            >= limits["searches"]
        ):

            user.free_trial_used = True

            db.session.commit()

            return False

        return True

    # =================================================
    # PAID PLANS
    # =================================================

    # ---------------------------------------------
    # SUBSCRIPTION MUST BE ACTIVE
    # ---------------------------------------------

    if (
        user.subscription_status
        != "active"
    ):

        return False

    # ---------------------------------------------
    # SEARCH LIMIT
    # ---------------------------------------------

    if (
        user.searches_used
        >= limits["searches"]
    ):

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

            "subscription_status":
                "inactive",

            "subscription_expires_at":
                None,

            "subscription_expired":
                False,

        }

    # ---------------------------------------------
    # CHECK EXPIRY
    # ---------------------------------------------

    subscription_expired = (
        check_subscription_expiry(
            user
        )
    )

    # ---------------------------------------------
    # RESET ONLY IF ACTIVE
    # ---------------------------------------------

    if not subscription_expired:

        reset_usage_if_needed(
            user
        )

        # Re-check after usage reset.
        subscription_expired = (
            check_subscription_expiry(
                user
            )
        )

    plan = get_user_plan(
        user
    )

    limits = get_plan_limits(
        user
    )

    used = (
        user.searches_used
    )

    limit = (
        limits["searches"]
    )

    remaining = max(
        limit - used,
        0
    )

    # ---------------------------------------------
    # PAID EXPIRED USER
    #
    # Keep their actual plan visible but
    # remaining searches become 0.
    # ---------------------------------------------

    if subscription_expired:

        remaining = 0

    # ---------------------------------------------
    # EXPIRY DATE
    # ---------------------------------------------

    expires_at = (
        user.subscription_expires_at
    )

    expires_at_value = None

    if expires_at:

        expires_at_value = (
            expires_at.isoformat()
        )

    return {

        "plan": plan,

        "used": used,

        "limit": limit,

        "remaining": remaining,

        "results_per_search":
            limits[
                "results_per_search"
            ],

        "free_trial_used":
            bool(
                user.free_trial_used
            ),

        "subscription_status":
            (
                user.subscription_status
                or "inactive"
            ),

        "subscription_expires_at":
            expires_at_value,

        "subscription_expired":
            subscription_expired,

    }


# =====================================================
# CONSUME SEARCH
#
# Called ONLY after a successful NEW search.
# =====================================================

def consume_search(user):

    if not user:

        return False

    # ---------------------------------------------
    # NEVER CONSUME SEARCH FROM EXPIRED SUBSCRIPTION
    # ---------------------------------------------

    if check_subscription_expiry(
        user
    ):

        return False

    # ---------------------------------------------
    # RESET USAGE IF REQUIRED
    # ---------------------------------------------

    reset_usage_if_needed(
        user
    )

    # ---------------------------------------------
    # CHECK EXPIRY AGAIN
    # ---------------------------------------------

    if check_subscription_expiry(
        user
    ):

        return False

    plan = get_user_plan(
        user
    )

    limits = get_plan_limits(
        user
    )

    # =================================================
    # FREE PLAN
    # =================================================

    if plan == "free":

        # ---------------------------------------------
        # TRIAL ALREADY USED
        # ---------------------------------------------

        if user.free_trial_used:

            return False

        # ---------------------------------------------
        # LIMIT REACHED
        # ---------------------------------------------

        if (
            user.searches_used
            >= limits["searches"]
        ):

            user.free_trial_used = True

            db.session.commit()

            return False

        # ---------------------------------------------
        # USE ONE SEARCH
        # ---------------------------------------------

        user.searches_used += 1

        # ---------------------------------------------
        # 10TH SEARCH COMPLETED
        # ---------------------------------------------

        if (
            user.searches_used
            >= limits["searches"]
        ):

            user.free_trial_used = True

        db.session.commit()

        return True

    # =================================================
    # PAID PLANS
    # =================================================

    # ---------------------------------------------
    # SUBSCRIPTION MUST BE ACTIVE
    # ---------------------------------------------

    if (
        user.subscription_status
        != "active"
    ):

        return False

    # ---------------------------------------------
    # SEARCH LIMIT
    # ---------------------------------------------

    if (
        user.searches_used
        >= limits["searches"]
    ):

        return False

    # ---------------------------------------------
    # CONSUME ONE SEARCH
    # ---------------------------------------------

    user.searches_used += 1

    db.session.commit()

    return True


# =====================================================
# USAGE API
# =====================================================

@usage_bp.route(
    "/api/usage",
    methods=["GET"]
)
def usage():

    user = get_current_user()

    if not user:

        return jsonify({

            "success": False,

            "message":
                "Please login before "
                "viewing usage.",

        }), 401

    return jsonify({

        "success": True,

        "usage":
            get_usage(
                user
            ),

    })

