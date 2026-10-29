
from flask import (
    Blueprint,
    jsonify,
    request,
    session,
    render_template,
)

from extensions import db
from models.user import User


plans_bp = Blueprint("plans", __name__)


# =====================================================
# PLAN DETAILS
# =====================================================

PLAN_DETAILS = {
    "free": {
        "name": "Free Plan",
        "searches": 10,
        "price": 0,
        "billing": "free",
    },
    "pro": {
        "name": "Pro",
        "searches": 500,
        "price": 9,
        "billing": "monthly",
    },
    "business": {
        "name": "Business",
        "searches": 1000,
        "price": 24,
        "billing": "monthly",
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
        return None

    return db.session.get(User, user_id)


# =====================================================
# PRICING PAGE
# =====================================================

@plans_bp.route("/pricing", methods=["GET"])
def pricing():
    return render_template(
        "pricing.html",
        current_user=session.get("user") or {},
    )


# =====================================================
# GET PLANS
# =====================================================

@plans_bp.route("/api/plans", methods=["GET"])
def get_plans():
    user = get_current_user()

    current_plan = "free"
    subscription_status = "inactive"
    free_trial_used = False
    subscription_expires_at = None

    if user:
        current_plan = (
            user.plan or "free"
        ).strip().lower()

        if current_plan not in PLAN_DETAILS:
            current_plan = "free"

        subscription_status = (
            user.subscription_status or "inactive"
        ).strip().lower()

        free_trial_used = bool(user.free_trial_used)

        if user.subscription_expires_at:
            subscription_expires_at = (
                user.subscription_expires_at.isoformat()
            )

    return jsonify({
        "success": True,
        "plans": PLAN_DETAILS,
        "current_plan": current_plan,
        "subscription_status": subscription_status,
        "free_trial_used": free_trial_used,
        "subscription_expires_at": subscription_expires_at,
    })


# =====================================================
# SELECT PLAN
# =====================================================

@plans_bp.route("/api/plans/select", methods=["POST"])
def select_plan():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please login before selecting a plan.",
        }), 401

    data = request.get_json(silent=True) or {}

    plan = str(
        data.get("plan", "")
    ).strip().lower()

    if plan not in PLAN_DETAILS:
        return jsonify({
            "success": False,
            "message": "Invalid plan selected.",
        }), 400

    # =================================================
    # PAID PLANS
    # Payment must be verified by the backend.
    # =================================================

    if plan in ("pro", "business"):
        return jsonify({
            "success": False,
            "message": "Please complete payment to activate this plan.",
            "redirect": f"/checkout?plan={plan}",
        }), 403

    # =================================================
    # FREE PLAN
    # =================================================

    if user.free_trial_used:
        return jsonify({
            "success": False,
            "message": (
                "Your Free trial has already been used. "
                "Please upgrade to Pro or Business."
            ),
            "plan": user.plan or "free",
            "free_trial_used": True,
        }), 403

    if (user.plan or "free").strip().lower() == "free":
        return jsonify({
            "success": True,
            "message": "You are already using the Free Plan.",
            "plan": "free",
            "plan_name": PLAN_DETAILS["free"]["name"],
            "searches": PLAN_DETAILS["free"]["searches"],
            "searches_used": user.searches_used,
            "searches_remaining": max(
                PLAN_DETAILS["free"]["searches"]
                - (user.searches_used or 0),
                0,
            ),
        })

    return jsonify({
        "success": False,
        "message": (
            "The Free Plan is available only as a one-time trial. "
            "Please continue with your current paid plan."
        ),
        "plan": user.plan or "free",
    }), 403
