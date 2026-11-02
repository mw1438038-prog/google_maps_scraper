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

PLAN_RANK = {
    "free": 0,
    "pro": 1,
    "business": 2,
}
