
from urllib.parse import urlencode
from urllib.parse import urlparse

import requests

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
FREEMIUS_API_BASE = "https://api.freemius.com/v1"


PLAN_DETAILS = {
    "free": {
        "name": "Free Plan",
        "price": 0,
        "searches": 10,
        
    },
    "pro": {
        "name": "Pro Plan",
        "price": 9,
        "searches": 500,
        
    },
    "business": {
        "name": "Business Plan",
        "price": 24,
        "searches": 1000,
        
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


def _freemius_post(path, token, payload):
    response = requests.post(
        f"{FREEMIUS_API_BASE}/{path.lstrip('/')}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


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

    is_plan_change = (
        (user.plan or "free").lower() in ("pro", "business")
        and (user.subscription_status or "").lower() == "active"
        and (user.plan or "").lower() != plan
    )

    return render_template(
        "checkout.html",
        user=user,
        plan=plan,
        plan_data=PLAN_DETAILS[plan],
        is_plan_change=is_plan_change,
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

    current_plan = (user.plan or "free").strip().lower()
    active_subscription = (
        current_plan in ("pro", "business")
        and (user.subscription_status or "").strip().lower() == "active"
    )

    if active_subscription and current_plan == plan:
        return {
            "success": False,
            "message": "You are already subscribed to this plan.",
        }, 400

    product_id = str(
        current_app.config.get("FREEMIUS_PRODUCT_ID") or ""
    ).strip()
    token = str(
        current_app.config.get("FREEMIUS_API_BEARER_TOKEN") or ""
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

    if active_subscription:
        license_id = str(
            user.payment_reference
            if user.payment_provider == "freemius"
            else ""
        ).strip()
        if not token or not license_id:
            current_app.logger.error(
                "Active Freemius subscription is missing its API token or license ID."
            )
            return {
                "success": False,
                "message": (
                    "Could not find your current Freemius subscription. "
                    "Please contact support before changing plans."
                ),
            }, 409

        try:
            checkout_data = _freemius_post(
                f"products/{product_id}/licenses/{license_id}/checkout/link.json",
                token,
                {
                    "plan_id": int(plan_id),
                    "billing_cycle": "monthly",
                    "quota": 1,
                    "currency": "usd",
                },
            )
            checkout_url = checkout_data.get("url")
            parsed_checkout = urlparse(checkout_url or "")
            if (
                not isinstance(checkout_url, str)
                or parsed_checkout.scheme != "https"
                or not parsed_checkout.hostname
                or not parsed_checkout.hostname.endswith(".freemius.com")
            ):
                raise ValueError("Freemius returned an invalid checkout URL.")
        except (requests.RequestException, ValueError, AttributeError):
            current_app.logger.exception(
                "Could not create a Freemius plan change checkout link."
            )
            return {
                "success": False,
                "message": (
                    "Could not start the plan change. Please try again or "
                    "contact support."
                ),
            }, 502

        return {
            "success": True,
            "checkout_url": checkout_url,
            "plan_change": True,
        }, 200

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

    if user.payment_provider != "freemius":
        return redirect(url_for("plans.pricing"))

    product_id = str(
        current_app.config.get("FREEMIUS_PRODUCT_ID") or ""
    ).strip()
    token = str(
        current_app.config.get("FREEMIUS_API_BEARER_TOKEN") or ""
    ).strip()

    if not product_id or not token:
        current_app.logger.error(
            "Freemius customer portal is missing API configuration."
        )
        return redirect(url_for("profile.profile"))

    try:
        portal_data = _freemius_post(
            f"products/{product_id}/portal/login.json",
            token,
            {"email": user.email},
        )
        portal_link = portal_data.get("link")

        if not isinstance(portal_link, str):
            raise ValueError("Freemius did not return a portal link.")

        parsed_link = urlparse(portal_link)
        if (
            parsed_link.scheme != "https"
            or not parsed_link.hostname
            or not parsed_link.hostname.endswith(".freemius.com")
        ):
            raise ValueError("Freemius returned an invalid portal link.")

        return redirect(portal_link)

    except (requests.RequestException, ValueError, AttributeError):
        current_app.logger.exception(
            "Could not create a Freemius customer portal link."
        )
        return redirect(url_for("profile.profile"))
