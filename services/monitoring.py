import hashlib
import math
import re
import time
import uuid
from datetime import datetime

from flask import current_app, g, has_request_context, request
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from extensions import db
from models.component_health import ComponentHealth
from models.error_event import ErrorEvent
from models.request_metric import RequestMetric
from services.logging_config import sanitize_log_value


_CATEGORY_COMPONENT = {
    "google_places": "google_places",
    "google": "google_places",
    "google_quota": "google_places",
    "google_auth": "google_places",
    "neon": "neon",
    "database": "neon",
    "auth": "authentication",
    "authentication": "authentication",
    "search": "search",
    "freemius": "freemius",
    "checkout": "freemius",
    "webhook": "freemius",
    "payment": "freemius",
    "export": "export",
    "application": "flask",
    "flask": "flask",
    "system": "flask",
}
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]")


def sanitize_summary(value):
    return sanitize_log_value(value)


def _now():
    return datetime.utcnow()


def _request_fields():
    if not has_request_context():
        return "", "unknown", None, "flask"
    rule = getattr(request, "url_rule", None)
    route_template = rule.rule if rule is not None else "unmatched"
    endpoint = (request.endpoint or "").lower()
    component = next(
        (value for key, value in _CATEGORY_COMPONENT.items() if key in endpoint),
        "flask",
    )
    return (
        getattr(g, "request_id", ""),
        route_template[:255],
        getattr(g, "response_status", None),
        component,
    )


def _request_duration_ms():
    try:
        started_at = getattr(g, "request_started_at", None)
        if (
            isinstance(started_at, bool)
            or not isinstance(started_at, (int, float))
            or not math.isfinite(started_at)
        ):
            return None
        elapsed_ms = max(0, (time.perf_counter() - started_at) * 1000)
        if not math.isfinite(elapsed_ms):
            return None
        return int(elapsed_ms)
    except Exception:
        return None


def _log_monitoring_failure(message, error):
    try:
        current_app.logger.error(
            message,
            extra={
                "category": "monitoring",
                "monitoring_exception_type": type(error).__name__,
            },
        )
    except Exception:
        pass


def _category_component(category):
    normalized = _SAFE_NAME_RE.sub("", str(category or "application").lower())[:48]
    return normalized or "application", _CATEGORY_COMPONENT.get(normalized, "flask")


def _route_error_category():
    endpoint = (request.endpoint or "").lower()
    return next((
        label for label in (
            "search", "export", "freemius", "checkout", "payment",
            "auth", "usage", "locations",
        ) if label in endpoint
    ), "application")


def _persist_error(values):
    table = ErrorEvent.__table__
    engine = db.engine
    dialect = engine.dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.request_id, table.c.fingerprint],
            set_={
                "last_seen_at": statement.excluded.last_seen_at,
                "occurrence_count": table.c.occurrence_count + 1,
            },
        )
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.request_id, table.c.fingerprint],
            set_={
                "last_seen_at": statement.excluded.last_seen_at,
                "occurrence_count": table.c.occurrence_count + 1,
            },
        )
    else:
        statement = table.insert().values(**values)
    with engine.begin() as connection:
        return connection.execute(statement.returning(table.c.id)).scalar_one()


def record_error(category, severity, summary, exception=None, status=None):
    """Persist a sanitized error independently; never disrupt the request."""
    if not has_request_context():
        return False

    category, inferred_component = _category_component(category)
    request_id, route, response_status, route_component = _request_fields()
    if not request_id:
        request_id = str(uuid.uuid4())
        g.request_id = request_id
    component = (
        inferred_component
        if inferred_component != "flask" or category in {"application", "system", "flask"}
        else route_component
    )
    exception_type = None
    if exception is not None:
        exception_type = _SAFE_NAME_RE.sub("", type(exception).__name__)[:100]
    status = status if status is not None else response_status
    now = _now()
    fingerprint_source = "|".join((
        component,
        category,
        route,
        exception_type or "",
    ))
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    values = {
        "event_timestamp": now,
        "severity": str(severity or "ERROR").upper()[:16],
        "component": component,
        "category": category,
        "route_template": route,
        "http_status": status,
        "request_id": request_id,
        "safe_summary": sanitize_summary(summary) or "Application error",
        "exception_type": exception_type,
        "fingerprint": fingerprint,
        "first_seen_at": now,
        "last_seen_at": now,
        "occurrence_count": 1,
    }
    g.monitoring_event_recorded = True
    try:
        event_id = _persist_error(values)
        _update_health_observation(
            component,
            success=False,
            source="observed_error",
            detail=values["safe_summary"],
            status=(
                "unavailable"
                if (
                    category.endswith("auth")
                    or status in {401, 403, 503}
                    or values["severity"] == "CRITICAL"
                )
                else "degraded"
            ),
            last_failure_event_id=event_id,
        )
        current_app.logger.log(
            {
                "WARNING": 30,
                "ERROR": 40,
                "CRITICAL": 50,
            }.get(values["severity"], 40),
            values["safe_summary"],
            extra={
                "category": category,
                "monitoring_recorded": True,
                "monitoring_exception_type": exception_type,
            },
        )
        return True
    except Exception as persist_error:
        current_app.logger.error(
            "Monitoring event could not be persisted.",
            extra={"category": "monitoring", "monitoring_exception_type": type(persist_error).__name__},
        )
        return False


def _update_health_observation(
    component,
    success,
    source,
    detail=None,
    status=None,
    last_failure_event_id=None,
):
    now = _now()
    safe_detail = sanitize_summary(detail) if detail else None
    table = ComponentHealth.__table__
    values = {
        "component": component,
        "status": "healthy" if success else (status or "degraded"),
        "last_checked_at": now,
        "last_success_at": now if success else None,
        "last_failure_at": None if success else now,
        "last_failure_event_id": last_failure_event_id,
        "check_source": str(source)[:48],
        "safe_status_detail": safe_detail,
    }
    dialect = db.engine.dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.component],
            set_={
                "status": statement.excluded.status,
                "last_checked_at": statement.excluded.last_checked_at,
                "last_success_at": db.func.coalesce(
                    statement.excluded.last_success_at, table.c.last_success_at
                ),
                "last_failure_at": db.func.coalesce(
                    statement.excluded.last_failure_at, table.c.last_failure_at
                ),
                "last_failure_event_id": db.func.coalesce(
                    statement.excluded.last_failure_event_id,
                    table.c.last_failure_event_id,
                ),
                "check_source": statement.excluded.check_source,
                "safe_status_detail": statement.excluded.safe_status_detail,
            },
        )
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.component],
            set_={
                "status": statement.excluded.status,
                "last_checked_at": statement.excluded.last_checked_at,
                "last_success_at": db.func.coalesce(
                    statement.excluded.last_success_at, table.c.last_success_at
                ),
                "last_failure_at": db.func.coalesce(
                    statement.excluded.last_failure_at, table.c.last_failure_at
                ),
                "last_failure_event_id": db.func.coalesce(
                    statement.excluded.last_failure_event_id,
                    table.c.last_failure_event_id,
                ),
                "check_source": statement.excluded.check_source,
                "safe_status_detail": statement.excluded.safe_status_detail,
            },
        )
    else:
        statement = table.insert().values(**values)
    with db.engine.begin() as connection:
        connection.execute(statement)


def mark_component_healthy_in_session(component, source):
    """Include a successful observation in an existing application transaction."""
    record = db.session.get(ComponentHealth, component)
    if record is None:
        record = ComponentHealth(component=component)
        db.session.add(record)
    now = _now()
    record.status = "healthy"
    record.last_checked_at = now
    record.last_success_at = now
    record.check_source = str(source)[:48]
    record.safe_status_detail = "Recent successful integration activity was observed."
    return record


def _persist_metric(values):
    with db.engine.begin() as connection:
        connection.execute(RequestMetric.__table__.insert().values(**values))


def record_request_outcome(outcome, status=None):
    if not has_request_context():
        return False
    request_id, route, response_status, component = _request_fields()
    duration_ms = _request_duration_ms()
    values = {
        "event_timestamp": _now(),
        "request_id": request_id,
        "route_template": route,
        "http_status": status or response_status or 500,
        "duration_ms": duration_ms if duration_ms is not None else 0,
        "outcome": str(outcome)[:32],
        "component": component,
    }
    try:
        _persist_metric(values)
        return True
    except Exception as error:
        _log_monitoring_failure("Monitoring metric could not be persisted.", error)
        return False


def initialize_request_tracking(app):
    @app.before_request
    def _monitoring_request_start():
        g.request_started_at = None
        try:
            g.request_started_at = time.perf_counter()
        except Exception as error:
            _log_monitoring_failure("Monitoring request timing setup failed.", error)
        try:
            g.request_id = str(uuid.uuid4())
        except Exception as error:
            _log_monitoring_failure("Monitoring request ID setup failed.", error)

    @app.after_request
    def _monitoring_request_finish(response):
        try:
            g.response_status = response.status_code
            response.headers["X-Request-ID"] = getattr(g, "request_id", "")
            endpoint = (request.endpoint or "").lower()
            duration_ms = _request_duration_ms()
            threshold = int(app.config.get("MONITORING_SLOW_REQUEST_MS", 2000))
            is_failed_search = (
                "search" in endpoint
                and request.method in {"POST", "PUT"}
                and response.status_code >= 400
            )
            if response.status_code >= 500 and not getattr(
                g, "monitoring_event_recorded", False
            ):
                category = _route_error_category()
                record_error(
                    category,
                    "ERROR",
                    "Request returned an internal error.",
                    status=response.status_code,
                )
            if is_failed_search:
                record_request_outcome("failed_search", response.status_code)
            if duration_ms is not None and duration_ms >= threshold:
                record_request_outcome("slow_request", response.status_code)
        except Exception as error:
            _log_monitoring_failure("Monitoring request finalization failed.", error)
        return response

    from flask import got_request_exception

    def _record_unhandled(sender, exception, **extra):
        # Flask emits this while the request context is active.
        try:
            from sqlalchemy.exc import SQLAlchemyError
            category = "neon" if isinstance(exception, SQLAlchemyError) else _route_error_category()
            record_error(
                category,
                "CRITICAL" if isinstance(exception, (MemoryError, SystemError)) else "ERROR",
                "Unhandled request exception.",
                exception=exception,
                status=500,
            )
        except Exception as error:
            _log_monitoring_failure("Monitoring exception tracking failed.", error)

    got_request_exception.connect(_record_unhandled, app, weak=False)
