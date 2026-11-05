"""Shared search allowances for each subscription plan."""

PLAN_LIMITS = {
    "free": {
        "searches": 10,
        "results_per_search": 20,
    },
    "pro": {
        "searches": 1000,
        "results_per_search": None,
        "duration_days": 30,
    },
    "business": {
        "searches": None,
        "results_per_search": None,
        "duration_days": 30,
    },
}

PLAN_DETAILS = {
    "free": {
        "name": "Free Plan",
        "searches": PLAN_LIMITS["free"]["searches"],
        "price": 0,
        "billing": "free",
    },
    "pro": {
        "name": "Pro Plan",
        "searches": PLAN_LIMITS["pro"]["searches"],
        "price": 9,
        "billing": "monthly",
    },
    "business": {
        "name": "Business Plan",
        "searches": PLAN_LIMITS["business"]["searches"],
        "price": 24,
        "billing": "monthly",
    },
}

FREEMIUS_PLAN_ID_SETTINGS = {
    "pro": "FREEMIUS_PRO_PLAN_ID",
    "business": "FREEMIUS_BUSINESS_PLAN_ID",
}

PLAN_RANK = {
    "free": 0,
    "pro": 1,
    "business": 2,
}
