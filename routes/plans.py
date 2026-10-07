
from flask import (
    Blueprint,
    jsonify,
    request,
    session,
    render_template,
)

from extensions import db
from models.user import User


plans_bp = Blueprint(
    "plans",
    __name__,
)


PLAN_DETAILS = {
    "free": {
        "name": "Free Plan",
        "searches": 10,
        "results_per_search": 15,
        "price": 0,
    },

    "pro": {
        "name": "Pro Plan",
        "searches": 100,
        "results_per_search": 100,
        "price": 12,
    },

    "business": {
        "name": "Business Plan",
        "searches": 500,
        "results_per_search": 200,
        "price": 29,
    },
}


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


@plans_bp.route(
    "/pricing",
    methods=["GET"]
)
def pricing():

    return render_template(
        "pricing.html"
    )


@plans_bp.route(
    "/api/plans",
    methods=["GET"]
)
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
            user.subscription_status
            or "inactive"
        ).strip().lower()

        free_trial_used = bool(
            user.free_trial_used
        )

        if user.subscription_expires_at:

            subscription_expires_at = (
                user.subscription_expires_at.isoformat()
            )

    return jsonify({

        "success": True,

        "plans": PLAN_DETAILS,

        "current_plan": current_plan,

        "subscription_status":
            subscription_status,

        "free_trial_used":
            free_trial_used,

        "subscription_expires_at":
            subscription_expires_at,

    })


@plans_bp.route(
    "/api/plans/select",
    methods=["POST"]
)
def select_plan():

    user = get_current_user()

    if not user:

        return jsonify({

            "success": False,

            "message": (
                "Please login before "
                "selecting a plan."
            ),

        }), 401

    data = (
        request.get_json(
            silent=True
        ) or {}
    )

    plan = str(
        data.get(
            "plan",
            ""
        )
    ).strip().lower()

    if plan not in PLAN_DETAILS:

        return jsonify({

            "success": False,

            "message": (
                "Invalid plan selected."
            ),

        }), 400

    # =================================================
    # PAID PLANS
    # =================================================

    if plan in (
        "pro",
        "business",
    ):

        return jsonify({

            "success": False,

            "message": (
                "Paid plans require "
                "verified payment."
            ),

            "redirect": (
                f"/checkout?plan={plan}"
            ),

        }), 403

    # =================================================
    # FREE PLAN
    # =================================================

    if plan == "free":

        # ---------------------------------------------
        # FREE TRIAL ALREADY USED
        # ---------------------------------------------

        if user.free_trial_used:

            return jsonify({

                "success": False,

                "message": (
                    "Your Free trial has "
                    "already been used. "
                    "Please upgrade to "
                    "Pro or Business."
                ),

                "plan":
                    user.plan or "free",

                "free_trial_used":
                    True,

            }), 403

        # ---------------------------------------------
        # ALREADY ON FREE
        # ---------------------------------------------

        if (
            (user.plan or "free")
            .strip()
            .lower()
            == "free"
        ):

            return jsonify({

                "success": True,

                "message": (
                    "You are already "
                    "using the Free Plan."
                ),

                "plan": "free",

                "plan_name": (
                    PLAN_DETAILS[
                        "free"
                    ]["name"]
                ),

                "searches": (
                    PLAN_DETAILS[
                        "free"
                    ]["searches"]
                ),

                "results_per_search": (
                    PLAN_DETAILS[
                        "free"
                    ]["results_per_search"]
                ),

                "searches_used": (
                    user.searches_used
                ),

                "searches_remaining": max(
                    PLAN_DETAILS[
                        "free"
                    ]["searches"]
                    - user.searches_used,
                    0
                ),

            })

        # ---------------------------------------------
        # PAID PLAN -> FREE NOT ALLOWED
        # ---------------------------------------------

        return jsonify({

            "success": False,

            "message": (
                "The Free Plan is available "
                "only as a one-time trial. "
                "Please continue with your "
                "current paid plan."
            ),

            "plan": (
                user.plan or "free"
            ),

        }), 403

    return jsonify({

        "success": False,

        "message": (
            "Unable to select plan."
        ),

    }), 400

