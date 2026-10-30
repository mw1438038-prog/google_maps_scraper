"""Shared search allowances for each subscription plan."""

PLAN_LIMITS = {
    "free": {
        "searches": 10,
        "results_per_search": 15,
    },
    "pro": {
        "searches": 500,
        "results_per_search": 100,
        "duration_days": 30,
    },
    "business": {
        "searches": 1000,
        "results_per_search": 200,
        "duration_days": 30,
    },
}

PLAN_RANK = {
    "free": 0,
    "pro": 1,
    "business": 2,
}
