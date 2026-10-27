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
from routes.usage import get_usage


profile_bp = Blueprint(
    "profile",
    __name__,
    url_prefix="/profile"
)


@profile_bp.route("/")
def profile():
    user = _get_current_user()
    if user is None:
        return redirect(url_for("auth.google_login"))

    return _render_dashboard(user, "dashboard")


@profile_bp.route("/account")
def account():
    user = _get_current_user()
    if user is None:
        return redirect(url_for("auth.google_login"))

    return render_template("account.html", user=_get_profile_data(user))


@profile_bp.route("/<string:view>", methods=["GET", "POST"])
def section(view):
    allowed_views = {"leads", "history", "exports", "usage", "settings", "help"}
    if view not in allowed_views:
        abort(404)

    user = _get_current_user()
    if user is None:
        return redirect(url_for("auth.google_login"))

    settings_message = ""
    settings_error = ""

    if view == "settings" and request.method == "POST":
        display_name = str(request.form.get("name", "")).strip()
        if not display_name or len(display_name) > 80:
            settings_error = "Enter a name between 1 and 80 characters."
        else:
            user.name = display_name
            db.session.commit()
            session_user = session.get("user", {})
            if isinstance(session_user, dict):
                session_user["name"] = display_name
                session["user"] = session_user
            settings_message = "Your profile settings have been saved."

    dashboard_data = _get_dashboard_data(user)
    return render_template(
        "profile.html",
        user=_get_profile_data(user),
        view=view,
        dashboard=dashboard_data,
        settings_message=settings_message,
        settings_error=settings_error,
    )


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


def _render_dashboard(user, view):
    return render_template(
        "profile.html",
        user=_get_profile_data(user),
        view=view,
        dashboard=_get_dashboard_data(user),
        settings_message="",
        settings_error="",
    )


def _get_profile_data(user):
    usage = get_usage(user)
    searches_used = usage["used"]
    plan = (user.plan or "free").lower()
    searches_limit = usage["limit"]
    usage_percentage = min(usage["used"] / max(usage["limit"], 1) * 100, 100)
    searches_remaining = usage["remaining"]
    plan_names = {
        "free": "Free",
        "pro": "Pro",
        "business": "Business"
    }
    plan_name = plan_names.get(plan, plan.capitalize())
    member_since = user.created_at.strftime("%B %Y") if user.created_at else None
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
        "subscription_status": user.subscription_status or "inactive",
        "member_since": member_since,
        "subscription_expires": subscription_expires,
        "payment_provider": user.payment_provider,
    }


def _get_dashboard_data(user):
    history_query = SearchHistory.query.filter_by(user_id=user.id)
    totals = db.session.query(
        func.count(SearchHistory.id),
        func.coalesce(func.sum(SearchHistory.result_count), 0),
        func.coalesce(func.sum(SearchHistory.exported_leads), 0),
    ).filter(SearchHistory.user_id == user.id).one()

    recent_history = history_query.order_by(
        SearchHistory.created_at.desc()
    ).limit(50).all()

    today = datetime.utcnow().date()
    week_dates = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    week_start = datetime.combine(week_dates[0], datetime.min.time())
    week_counts = {day: 0 for day in week_dates}
    for record in history_query.filter(
        SearchHistory.created_at >= week_start
    ).all():
        created_day = record.created_at.date()
        if created_day in week_counts:
            week_counts[created_day] += 1

    max_week_count = max(week_counts.values(), default=0)
    weekly_activity = [
        {
            "label": day.strftime("%a"),
            "count": week_counts[day],
            "height": round(week_counts[day] / max_week_count * 100) if max_week_count else 0,
        }
        for day in week_dates
    ]

    recent_leads = []
    all_leads = []
    seen_leads = set()
    for record in recent_history:
        for lead in record.results or []:
            name = str(lead.get("name") or "").strip()
            address = str(lead.get("address") or "").strip()
            if not name:
                continue
            lead_key = str(lead.get("place_id") or f"{name}|{address}")
            if lead_key in seen_leads:
                continue
            seen_leads.add(lead_key)
            lead_row = {
                "name": name,
                "address": address,
                "rating": lead.get("rating"),
                "reviews": lead.get("reviews"),
                "maps_url": lead.get("maps_url"),
                "query": f"{record.keyword} · {record.city}",
                "added": record.created_at.strftime("%b %d, %Y"),
            }
            all_leads.append(lead_row)
            if len(recent_leads) < 6:
                recent_leads.append(lead_row)

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
            "created_at": record.created_at.strftime("%b %d, %Y · %I:%M %p"),
            "last_exported_at": (
                record.last_exported_at.strftime("%b %d, %Y · %I:%M %p")
                if record.last_exported_at
                else None
            ),
        }
        for record in recent_history
    ]

    return {
        "total_searches": int(totals[0] or 0),
        "total_leads": int(totals[1] or 0),
        "exported_leads": int(totals[2] or 0),
        "recent_leads": recent_leads,
        "all_leads": all_leads[:100],
        "history": history_rows,
        "exports": history_rows,
        "weekly_activity": weekly_activity,
        "max_week_count": max_week_count,
    }
