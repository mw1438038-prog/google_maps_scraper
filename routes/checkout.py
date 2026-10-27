
from urllib.parse import urlencode

from flask import (
    Blueprint,
    current_app,
    render_template,
    session,
    redirect,
    url_for,
    request,
)

from extensions import db
from models.user import User


checkout_bp = Blueprint("checkout", __name__)


PLAN_DETAILS = {
    "free": {
        "name": "Free Plan",
        "price": 0,
        "searches": 10,
        "results_per_search": 15,
    },
    "pro": {
        "name": "Pro Plan",
        "price": 9,
        "searches": 500,
        "results_per_search": 100,
    },
    "business": {
        "name": "Business Plan",
        "price": 24,
        "searches": 1000,
        "results_per_search": 200,
    },
}


def get_current_user():
    user_data = session.get("user")

    if not user_data or not user_data.get("id"):
        return None

    return db.session.get(User, user_data["id"])


def get_freemius_plan_id(plan):
    setting_name = {
        "pro": "FREEMIUS_PRO_PLAN_ID",
        "business": "FREEMIUS_BUSINESS_PLAN_ID",
    }.get(plan)

    if not setting_name:
        return ""

    return str(current_app.config.get(setting_name) or "").strip()


@checkout_bp.route("/checkout", methods=["GET"])
def checkout():
    user = get_current_user()

    if not user:
        return redirect(url_for("auth.google_login"))

    plan = request.args.get("plan", "").strip().lower()

    if plan not in ("pro", "business"):
        return redirect(url_for("pricing_page"))

    if (
        (user.plan or "free").lower() == plan
        and (user.subscription_status or "").lower() == "active"
    ):
        return redirect(url_for("leads"))

    return render_template(
        "checkout.html",
        user=user,
        plan=plan,
        plan_data=PLAN_DETAILS[plan],
    )


@checkout_bp.route("/api/checkout/start", methods=["POST"])
def start_checkout():
    user = get_current_user()

    if not user:
        return {
            "success": False,
            "message": "Please log in before checkout.",
        }, 401

    data = request.get_json(silent=True) or {}
    plan = str(data.get("plan", "")).strip().lower()

    if plan not in ("pro", "business"):
        return {
            "success": False,
            "message": "Invalid paid plan.",
        }, 400

    if (
        (user.plan or "free").lower() == plan
        and (user.subscription_status or "").lower() == "active"
    ):
        return {
            "success": False,
            "message": "You are already subscribed to this plan.",
        }, 400

    product_id = str(
        current_app.config.get("FREEMIUS_PRODUCT_ID") or ""
    ).strip()

    plan_id = get_freemius_plan_id(plan)

    if not product_id or not plan_id:
        current_app.logger.error(
            "Freemius product ID or plan ID is missing."
        )
        return {
            "success": False,
            "message": "Freemius checkout is not configured yet.",
        }, 503

    # Hosted checkout: the user email is URL-encoded.
    checkout_url = (
        f"https://checkout.freemius.com/product/{product_id}/plan/{plan_id}/"
        f"?{urlencode({'user_email': user.email, 'readonly_user': 'true'})}"
    )

    return {
        "success": True,
        "checkout_url": checkout_url,
    }, 200


@checkout_bp.route("/billing/portal", methods=["GET"])
def billing_portal():
    user = get_current_user()

    if not user:
        return redirect(url_for("auth.google_login"))

    # Customer portal integration can be added separately.
    return redirect(url_for("profile.profile"))
