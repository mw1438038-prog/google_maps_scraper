
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func

from extensions import db
from models.user import User
from models.search_history import SearchHistory
from models.exported_lead import ExportedLead
from routes.usage import get_usage


profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

LEADS_PER_PAGE = 10


class Pagination:
    """Pagination helper for My Leads."""

    def __init__(self, page, total, per_page=LEADS_PER_PAGE):
        self.per_page = per_page
        self.total = total
        self.pages = max(1, (total + per_page - 1) // per_page)
        self.page = min(max(1, page), self.pages)

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1

    @property
    def next_num(self):
        return self.page + 1

    def iter_pages(
        self,
        left_edge=1,
        left_current=1,
        right_current=2,
        right_edge=1,
    ):
        last = 0

        for number in range(1, self.pages + 1):
            if (
                number <= left_edge
                or (
                    number >= self.page - left_current
                    and number <= self.page + right_current
                )
                or number > self.pages - right_edge
            ):
                if last + 1 != number:
                    yield None

                yield number
                last = number


# =========================================================
# DASHBOARD
# =========================================================

@profile_bp.route("/")
def profile():
    user = _get_current_user()

    if user is None:
        return redirect(url_for("auth.google_login"))

    return _render_dashboard(user, "dashboard")


# =========================================================
# ACCOUNT
# =========================================================

@profile_bp.route("/account")
def account():
    user = _get_current_user()

    if user is None:
        return redirect(url_for("auth.google_login"))

    return render_template(
        "account.html",
        user=_get_profile_data(user),
    )


# =========================================================
# PROFILE SECTIONS
# =========================================================

@profile_bp.route("/<string:view>", methods=["GET"])
def section(view):
    allowed_views = {
        "leads",
        "history",
        "exports",
        "usage",
        "help",
        "subscription",
    }

    if view not in allowed_views:
        abort(404)

    user = _get_current_user()

    if user is None:
        return redirect(url_for("auth.google_login"))

    dashboard_data = _get_dashboard_data(user)
    pagination = None

    # -----------------------------------------------------
    # MY LEADS
    # -----------------------------------------------------

    if view == "leads":
        try:
            page = int(request.args.get("page", 1))
        except (TypeError, ValueError):
            page = 1

        page = max(1, page)

        leads_query = ExportedLead.query.filter_by(
            user_id=user.id
        )

        total_leads = leads_query.count()

        pagination = Pagination(
            page=page,
            total=total_leads,
            per_page=LEADS_PER_PAGE,
        )

        start = (pagination.page - 1) * LEADS_PER_PAGE

        exported_records = (
            leads_query
            .order_by(
                ExportedLead.created_at.desc(),
                ExportedLead.id.desc(),
            )
            .offset(start)
            .limit(LEADS_PER_PAGE)
            .all()
        )

        dashboard_data["all_leads"] = [
            {
                "id": lead.id,
                "name": lead.name,
                "address": lead.address,
                "phone": lead.phone,
                "website": lead.website,
                "email": lead.email,
                "facebook": lead.facebook,
                "instagram": lead.instagram,
                "linkedin": lead.linkedin,
                "twitter": lead.twitter,
                "other_social": lead.other_social,
                "rating": lead.rating,
                "reviews": lead.reviews,
                "maps_url": lead.maps_url,
                "query": _format_query(
                    lead.keyword,
                    lead.city,
                ),
                "added": (
                    lead.created_at.strftime("%b %d, %Y")
                    if lead.created_at
                    else "—"
                ),
            }
            for lead in exported_records
        ]

    # -----------------------------------------------------
    # PREPARE PROFILE DATA
    # -----------------------------------------------------

    profile_data = _get_profile_data(user)

    # -----------------------------------------------------
    # SUBSCRIPTION - SEPARATE HTML TEMPLATE
    # -----------------------------------------------------

    if view == "subscription":
        return render_template(
            "subscription.html",
            user=profile_data,
            view=view,
            dashboard=dashboard_data,
        )

    # -----------------------------------------------------
    # ALL OTHER PROFILE SECTIONS
    # -----------------------------------------------------

    return render_template(
        "profile.html",
        user=profile_data,
        view=view,
        dashboard=dashboard_data,
        pagination=pagination,
    )


# =========================================================
# CURRENT USER
# =========================================================

def _get_current_user():
    session_user = session.get("user")

    if not isinstance(session_user, dict):
        return None

    user_id = session_user.get("id")

    if not user_id:
        return None

    user = db.session.get(User, user_id)

    if user is None:
        session.clear()
        return None

    return user


# =========================================================
# DASHBOARD RENDER
# =========================================================

def _render_dashboard(user, view):
    return render_template(
        "profile.html",
        user=_get_profile_data(user),
        view=view,
        dashboard=_get_dashboard_data(user),
        pagination=None,
    )


# =========================================================
# USER PROFILE DATA
# =========================================================

def _get_profile_data(user):
    usage = get_usage(user)

    searches_used = usage["used"]
    plan = (user.plan or "free").lower()
    searches_limit = usage["limit"]

    usage_percentage = min(
        searches_used / max(searches_limit, 1) * 100,
        100,
    )

    searches_remaining = usage["remaining"]

    plan_names = {
        "free": "Free",
        "pro": "Pro",
        "business": "Business",
    }

    plan_name = plan_names.get(
        plan,
        plan.capitalize(),
    )

    member_since = (
        user.created_at.strftime("%B %Y")
        if user.created_at
        else None
    )

    subscription_expires = (
        user.subscription_expires_at.strftime("%d %b %Y")
        if user.subscription_expires_at
        else None
    )

    return {
        "id": user.id,
        "name": user.name or "User",
        "email": user.email,
        "picture": user.picture,
        "plan": plan,
        "plan_name": plan_name,
        "searches_used": searches_used,
        "searches_limit": searches_limit,
        "searches_remaining": searches_remaining,
        "usage_percentage": usage_percentage,
        "usage_percentage_display": f"{usage_percentage:g}",
        "subscription_status": (
            user.subscription_status or "inactive"
        ),
        "member_since": member_since,
        "subscription_expires": subscription_expires,
        "payment_provider": user.payment_provider,
    }


# =========================================================
# HELPERS
# =========================================================

def _format_query(keyword, city):
    keyword = str(keyword or "").strip()
    city = str(city or "").strip()

    if keyword and city:
        return f"{keyword} · {city}"

    return keyword or city or "Exported lead"


def _format_datetime(value):
    if not value:
        return "—"

    return value.strftime("%b %d, %Y · %I:%M %p")


# =========================================================
# DASHBOARD DATA
# =========================================================

def _get_dashboard_data(user):
    history_query = SearchHistory.query.filter_by(
        user_id=user.id
    )

    totals = db.session.query(
        func.count(SearchHistory.id),
        func.coalesce(
            func.sum(SearchHistory.result_count),
            0,
        ),
        func.coalesce(
            func.sum(SearchHistory.exported_leads),
            0,
        ),
    ).filter(
        SearchHistory.user_id == user.id
    ).one()

    recent_history = (
        history_query
        .order_by(SearchHistory.created_at.desc())
        .limit(50)
        .all()
    )

    # -----------------------------------------------------
    # LAST 7 DAYS ACTIVITY
    # -----------------------------------------------------

    today = datetime.utcnow().date()

    week_dates = [
        today - timedelta(days=offset)
        for offset in range(6, -1, -1)
    ]

    week_start = datetime.combine(
        week_dates[0],
        datetime.min.time(),
    )

    week_counts = {
        day: 0
        for day in week_dates
    }

    weekly_records = history_query.filter(
        SearchHistory.created_at >= week_start
    ).all()

    for record in weekly_records:
        if not record.created_at:
            continue

        created_day = record.created_at.date()

        if created_day in week_counts:
            week_counts[created_day] += 1

    max_week_count = max(
        week_counts.values(),
        default=0,
    )

    weekly_activity = [
        {
            "label": day.strftime("%a"),
            "count": week_counts[day],
            "height": (
                round(
                    week_counts[day]
                    / max_week_count
                    * 100
                )
                if max_week_count
                else 0
            ),
        }
        for day in week_dates
    ]

    # -----------------------------------------------------
    # EXPORTED LEADS ONLY
    # -----------------------------------------------------

    exported_query = ExportedLead.query.filter_by(
        user_id=user.id
    )

    recent_exported_records = (
        exported_query
        .order_by(
            ExportedLead.created_at.desc(),
            ExportedLead.id.desc(),
        )
        .limit(6)
        .all()
    )

    recent_leads = [
        {
            "name": lead.name,
            "address": lead.address,
            "rating": lead.rating,
            "reviews": lead.reviews,
            "maps_url": lead.maps_url,
            "query": _format_query(
                lead.keyword,
                lead.city,
            ),
            "added": (
                lead.created_at.strftime("%b %d, %Y")
                if lead.created_at
                else "—"
            ),
        }
        for lead in recent_exported_records
    ]

    # -----------------------------------------------------
    # SEARCH HISTORY AND EXPORT CENTER
    # -----------------------------------------------------

    history_rows = [
        {
            "id": record.id,
            "search_id": record.search_id,
            "keyword": record.keyword,
            "city": record.city,
            "country": record.country,
            "result_count": record.result_count,
            "export_count": record.export_count,
            "exported_leads": record.exported_leads,
            "created_at": _format_datetime(
                record.created_at
            ),
            "last_exported_at": (
                _format_datetime(record.last_exported_at)
                if record.last_exported_at
                else None
            ),
        }
        for record in recent_history
    ]

    actual_exported_count = exported_query.count()

    return {
        "total_searches": int(totals[0] or 0),
        "total_leads": int(totals[1] or 0),
        "exported_leads": actual_exported_count,
        "recent_leads": recent_leads,
        "all_leads": [],
        "history": history_rows,
        "exports": history_rows,
        "weekly_activity": weekly_activity,
        "max_week_count": max_week_count,
    }
