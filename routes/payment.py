
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    jsonify,
    session,
    request,
)

from extensions import db
from models.user import User


payment_bp = Blueprint(
    "payment",
    __name__,
)


# =====================================================
# TEST PAYMENT PLANS
# =====================================================

PLAN_DETAILS = {

    "pro": {
        "name": "Pro Plan",
        "price": 12,
        "searches": 100,
        "results_per_search": 100,
        "duration_days": 30,
    },

    "business": {
        "name": "Business Plan",
        "price": 29,
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
# TEST PAYMENT
# =====================================================

@payment_bp.route(
    "/api/payment/test",
    methods=["POST"]
)
def test_payment():

    user = get_current_user()

    if not user:

        return jsonify({

            "success": False,

            "message":
                "Please login before "
                "making a payment.",

        }), 401


    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    plan = str(
        data.get(
            "plan",
            ""
        )
    ).strip().lower()


    card_number = str(
        data.get(
            "card_number",
            ""
        )
    ).replace(
        " ",
        ""
    )


    expiry = str(
        data.get(
            "expiry",
            ""
        )
    ).strip()


    cvc = str(
        data.get(
            "cvc",
            ""
        )
    ).strip()


    card_name = str(
        data.get(
            "card_name",
            ""
        )
    ).strip()


    # =================================================
    # VALIDATE PLAN
    # =================================================

    if plan not in PLAN_DETAILS:

        return jsonify({

            "success": False,

            "message":
                "Invalid paid plan.",

        }), 400


    plan_data = PLAN_DETAILS[
        plan
    ]


    # =================================================
    # TEST CARD VALIDATION
    # =================================================

    # ONLY FOR LOCAL TESTING
    #
    # Test card:
    # 4242 4242 4242 4242
    #
    # No real card is processed.

    if card_number != (
        "4242424242424242"
    ):

        return jsonify({

            "success": False,

            "message": (
                "Test payment failed. "
                "Use test card "
                "4242 4242 4242 4242."
            ),

        }), 400


    if not expiry:

        return jsonify({

            "success": False,

            "message":
                "Enter card expiry date.",

        }), 400


    if (
        len(cvc) != 3
        or not cvc.isdigit()
    ):

        return jsonify({

            "success": False,

            "message":
                "Enter a valid "
                "3-digit test CVC.",

        }), 400


    if not card_name:

        return jsonify({

            "success": False,

            "message":
                "Enter cardholder name.",

        }), 400


    # =================================================
    # CURRENT SUBSCRIPTION STATUS
    # =================================================

    current_plan = (
        user.plan or "free"
    ).strip().lower()


    current_status = (
        user.subscription_status
        or "inactive"
    ).strip().lower()


    # =================================================
    # PREVENT SAME ACTIVE PLAN
    #
    # Active Pro -> Pro again = blocked
    # Active Business -> Business again = blocked
    #
    # Expired Pro -> Pro = allowed
    # Expired Business -> Business = allowed
    # =================================================

    if (
        current_plan == plan
        and current_status == "active"
    ):

        return jsonify({

            "success": False,

            "message": (
                f"You are already subscribed "
                f"to the {plan_data['name']}."
            ),

        }), 400


    # =================================================
    # PAYMENT REFERENCE
    # =================================================

    payment_reference = (

        f"TEST-{user.id}-"

        f"{plan.upper()}-"

        f"{int(datetime.utcnow().timestamp())}"

    )


    # =================================================
    # SUBSCRIPTION DATES
    # =================================================

    now = datetime.utcnow()


    # -------------------------------------------------
    # NEW 30-DAY PERIOD
    #
    # Whether this is:
    #
    # - New subscription
    # - Expired subscription renewal
    # - Plan change
    #
    # starts a fresh 30-day period.
    # -------------------------------------------------

    expires_at = (

        now

        + timedelta(
            days=plan_data[
                "duration_days"
            ]
        )

    )


    # =================================================
    # ACTIVATE / RENEW PLAN
    # =================================================

    user.plan = plan


    # -------------------------------------------------
    # NEW SEARCH PERIOD
    # -------------------------------------------------

    user.searches_used = 0


    user.searches_limit = (

        plan_data[
            "searches"
        ]

    )


    user.searches_reset_at = now


    # -------------------------------------------------
    # SUBSCRIPTION STATUS
    # -------------------------------------------------

    user.subscription_status = (
        "active"
    )


    # -------------------------------------------------
    # SUBSCRIPTION DATES
    # -------------------------------------------------

    user.subscription_started_at = now

    user.subscription_expires_at = (
        expires_at
    )


    # -------------------------------------------------
    # PAYMENT INFORMATION
    # -------------------------------------------------

    user.payment_provider = (
        "test"
    )

    user.payment_reference = (
        payment_reference
    )


    # IMPORTANT:
    #
    # free_trial_used is NOT changed.
    #
    # Therefore an old Free trial remains used.
    #
    # Example:
    #
    # Free 10/10
    #   ↓
    # Pro
    #   ↓
    # Pro expires
    #   ↓
    # Renew Pro
    #
    # Free trial remains permanently used.


    db.session.commit()


    # =================================================
    # DETERMINE ACTION
    # =================================================

    if (
        current_plan == plan
        and current_status == "expired"
    ):

        action = "renewed"

        message = (

            f"{plan_data['name']} "
            "renewed successfully."

        )

    else:

        action = "activated"

        message = (

            f"{plan_data['name']} "
            "activated successfully."

        )


    # =================================================
    # RESPONSE
    # =================================================

    return jsonify({

        "success": True,

        "message": message,

        "action": action,

        "payment": {

            "status": "paid",

            "provider": "test",

            "reference":
                payment_reference,

            "amount":
                plan_data[
                    "price"
                ],

            "currency": "USD",

        },

        "subscription": {

            "plan": plan,

            "plan_name":
                plan_data[
                    "name"
                ],

            "status": "active",

            "searches":
                plan_data[
                    "searches"
                ],

            "results_per_search":
                plan_data[
                    "results_per_search"
                ],

            "started_at":
                now.isoformat(),

            "expires_at":
                expires_at.isoformat(),

        }

    }), 200

