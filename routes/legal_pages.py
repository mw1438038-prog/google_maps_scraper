from flask import Flask, render_template


LEGAL_PAGES = {
    "privacy": {
        "title": "Privacy Policy",
        "description": (
            "How Somo LeadFinder handles account, search, subscription, and "
            "operational information."
        ),
        "endpoint": "privacy_policy",
        "template": "privacy_policy.html",
        "sections": [
            ("information-we-receive", "Information we receive"),
            ("cookies-and-sessions", "Cookies and sessions"),
            ("map-and-account-providers", "Map and account providers"),
            ("storage-sharing-retention", "Storage, sharing, and retention"),
            ("security", "Security"),
            ("your-choices-and-requests", "Your choices and requests"),
        ],
    },
    "terms": {
        "title": "Terms & Conditions",
        "description": (
            "The terms for using Somo LeadFinder, its search features, "
            "exports, and subscription plans."
        ),
        "endpoint": "terms_conditions",
        "template": "terms_conditions.html",
        "sections": [
            ("using-the-service", "Using the service"),
            ("accounts", "Accounts"),
            ("plans-quotas-restrictions", "Plans, quotas, and restrictions"),
            ("google-data-and-exports", "Google Maps Platform data and exports"),
            ("subscriptions-billing-cancellation", "Subscriptions, billing, and cancellation"),
            ("availability-suspension-termination", "Availability, suspension, and termination"),
            ("disclaimers-liability", "Disclaimers and limitation of liability"),
            ("contact-and-updates", "Contact and updates"),
        ],
    },
    "refund": {
        "title": "Refund & Cancellation Policy",
        "description": (
            "How to manage a Somo LeadFinder subscription and where to direct "
            "refund requests."
        ),
        "endpoint": "refund_cancellation_policy",
        "template": "refund_cancellation_policy.html",
        "sections": [
            ("refund-requests", "Refund requests"),
            ("manage-or-cancel", "Manage or cancel a subscription"),
            ("questions", "Questions"),
        ],
    },
    "cookies": {
        "title": "Cookie Policy",
        "description": (
            "Learn about essential session cookies and cookie controls for "
            "Somo LeadFinder."
        ),
        "endpoint": "cookie_policy",
        "template": "cookie_policy.html",
        "sections": [
            ("essential-session-cookies", "Essential session cookies"),
            ("google-authentication", "Google authentication"),
            ("security-and-functionality", "Security and functionality"),
            ("analytics-and-advertising", "Analytics and advertising"),
            ("managing-cookies", "Managing cookies"),
            ("contact-and-updates", "Contact and updates"),
        ],
    },
}

RELATED_LEGAL_PAGES = [
    ("privacy", "Privacy Policy", "privacy_policy"),
    ("terms", "Terms & Conditions", "terms_conditions"),
    ("refund", "Refund & Cancellation", "refund_cancellation_policy"),
    ("cookies", "Cookie Policy", "cookie_policy"),
]


def _render_legal_page(page_key: str):
    page = LEGAL_PAGES[page_key]
    return render_template(
        page["template"],
        legal_page=page,
        related_pages=[
            item for item in RELATED_LEGAL_PAGES if item[0] != page_key
        ],
        all_legal_pages=RELATED_LEGAL_PAGES,
    )


def privacy_policy():
    return _render_legal_page("privacy")


def terms_conditions():
    return _render_legal_page("terms")


def refund_cancellation_policy():
    return _render_legal_page("refund")


def cookie_policy():
    return _render_legal_page("cookies")


def register_legal_pages(app: Flask) -> None:
    app.add_url_rule(
        "/privacy-policy",
        endpoint="privacy_policy",
        view_func=privacy_policy,
    )
    app.add_url_rule(
        "/terms-conditions",
        endpoint="terms_conditions",
        view_func=terms_conditions,
    )
    app.add_url_rule(
        "/refund-cancellation-policy",
        endpoint="refund_cancellation_policy",
        view_func=refund_cancellation_policy,
    )
    app.add_url_rule(
        "/cookie-policy",
        endpoint="cookie_policy",
        view_func=cookie_policy,
    )
