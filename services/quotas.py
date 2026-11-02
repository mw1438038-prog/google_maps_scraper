from datetime import datetime, timezone

from sqlalchemy import update

from extensions import db
from models.user import User
from services.plan_limits import PLAN_LIMITS


def _as_utc_naive(value):
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def current_month_start(now=None):
    now = _as_utc_naive(now or datetime.now(timezone.utc))
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def refresh_free_quota(user, now=None, *, commit=True):
    if (user.plan or "free").strip().lower() != "free":
        return False

    period_start = current_month_start(now)
    result = db.session.execute(
        update(User)
        .where(
            User.id == user.id,
            User.plan == "free",
            User.searches_reset_at < period_start,
        )
        .values(
            searches_used=0,
            searches_limit=PLAN_LIMITS["free"]["searches"],
            searches_rollover_remaining=0,
            free_trial_used=False,
            searches_reset_at=period_start,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount and commit:
        db.session.commit()
    db.session.refresh(user)
    return bool(result.rowcount)


def expire_subscription_to_free(
    user,
    now=None,
    *,
    status="expired",
    commit=True,
):
    now = _as_utc_naive(now or datetime.now(timezone.utc))

    user.plan = "free"
    user.subscription_status = status
    user.searches_limit = PLAN_LIMITS["free"]["searches"]
    user.searches_used = PLAN_LIMITS["free"]["searches"]
    user.searches_rollover_remaining = 0
    user.free_trial_used = True
    user.searches_reset_at = current_month_start(now)
    if commit:
        db.session.commit()
