
from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    request,
    abort,
)

from extensions import db
from models.user import User


checkout_bp = Blueprint(
    "checkout",
    __name__,
)


# =====================================================
# PAID PLAN DETAILS
# =====================================================

PLAN_DETAILS = {

    "pro": {
        "name": "Pro Plan",
        "price": 12,
        "searches": 100,
        "results_per_search": 100,
    },

    "business": {
        "name": "Business Plan",
        "price": 29,
        "searches": 500,
        "results_per_search": 200,
    },

}


# =====================================================
# GET CURRENT USER
# =====================================================

def get_current_user():

    user_data = session.get("user")

    if not user_data:
        return None


    user_id = user_data.get("id")

    if not user_id:
        return None


    return db.session.get(
        User,
        user_id,
    )


# =====================================================
# CHECKOUT PAGE
# =====================================================

@checkout_bp.route(
    "/checkout",
    methods=["GET"],
)
def checkout():

    # =================================================
    # LOGIN REQUIRED
    # =================================================

    user = get_current_user()

    if not user:

        return redirect(
            url_for(
                "auth.google_login"
            )
        )


    # =================================================
    # GET PLAN FROM URL
    # =================================================

    plan = (
        request.args.get(
            "plan",
            "",
        )
        .strip()
        .lower()
    )


    # =================================================
    # ONLY PAID PLANS
    # =================================================

    if plan not in PLAN_DETAILS:

        return redirect(
            url_for(
                "plans.pricing"
            )
        )


    # =================================================
    # PLAN DETAILS
    # =================================================

    plan_data = PLAN_DETAILS[plan]


    # =================================================
    # CURRENT PLAN
    # =================================================

    current_plan = (
        user.plan or "free"
    ).strip().lower()


    # =================================================
    # ALREADY ON THIS PLAN
    # =================================================

    if current_plan == plan:

        return redirect(
            url_for(
                "leads"
            )
        )


    # =================================================
    # CHECKOUT
    # =================================================

    return render_template(
        "checkout.html",

        user=user,

        plan=plan,

        plan_data=plan_data,
    )


# =====================================================
# PAYMENT START
# =====================================================

@checkout_bp.route(
    "/api/checkout/start",
    methods=["POST"],
)
def start_checkout():

    # =================================================
    # LOGIN REQUIRED
    # =================================================

    user = get_current_user()

    if not user:

        return {
            "success": False,
            "message":
                "Please login before starting checkout.",
        }, 401


    # =================================================
    # REQUEST DATA
    # =================================================

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    plan = str(
        data.get(
            "plan",
            "",
        )
    ).strip().lower()


    # =================================================
    # VALIDATE PLAN
    # =================================================

    if plan not in PLAN_DETAILS:

        return {
            "success": False,
            "message":
                "Invalid paid plan.",
        }, 400


    # =================================================
    # CURRENT PLAN
    # =================================================

    current_plan = (
        user.plan or "free"
    ).strip().lower()


    # =================================================
    # ALREADY ACTIVE
    # =================================================

    if current_plan == plan:

        return {
            "success": False,
            "message":
                "You are already on this plan.",
        }, 400


    # =================================================
    # IMPORTANT SECURITY RULE
    # =================================================
    #
    # DO NOT activate the plan here.
    #
    # This endpoint will later create a payment
    # session with the payment provider.
    #
    # The plan will only be activated after
    # verified payment.
    #

    plan_data = PLAN_DETAILS[plan]


    return {
        "success": True,

        "message":
            "Checkout is ready for payment.",

        "plan":
            plan,

        "plan_name":
            plan_data["name"],

        "price":
            plan_data["price"],

        "currency":
            "USD",

        "searches":
            plan_data["searches"],

        "results_per_search":
            plan_data["results_per_search"],

        "payment_required":
            True,

    }, 200

