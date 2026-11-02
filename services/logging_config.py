import json
import logging
import re
import sys
import threading
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from flask import g, has_request_context


_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|authorization|cookie)"
    r"\s*[:=]\s*([^\s,;]+)"
)
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d(). -]{7,}\d)(?!\w)")


def sanitize_log_value(value):
    """Remove common credential and personal-data shapes from log text."""
    value = str(value or "")
    value = _BEARER_RE.sub("[REDACTED]", value)
    value = _SECRET_RE.sub(r"\1=[REDACTED]", value)
    value = _URL_RE.sub("[URL]", value)
    value = _EMAIL_RE.sub("[EMAIL]", value)
    value = _PHONE_RE.sub("[PHONE]", value)
    return value[:240]


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = (
                getattr(g, "request_id", "") if has_request_context() else ""
            )
        if not hasattr(record, "category"):
            record.category = "application"
        return True


class SafeJsonFormatter(logging.Formatter):
    """Serialize only safe fields; deliberately omits exception tracebacks."""

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "logger": record.name[:100],
            "request_id": getattr(record, "request_id", ""),
            "category": sanitize_log_value(getattr(record, "category", "application")),
            "message": sanitize_log_value(record.getMessage()),
        }
        exception = getattr(record, "monitoring_exception_type", None)
        if exception:
            payload["exception_type"] = str(exception)[:100]
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class MonitoringEventHandler(logging.Handler):
    """Persist request-scoped warning and higher log records safely."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self._state = threading.local()

    def emit(self, record):
        if (
            not has_request_context()
            or getattr(self._state, "active", False)
            or getattr(record, "monitoring_recorded", False)
            or getattr(record, "category", "") == "monitoring"
            or record.exc_info
        ):
            return
        self._state.active = True
        try:
            from services.monitoring import record_error

            level = (
                "CRITICAL" if record.levelno >= logging.CRITICAL
                else "ERROR" if record.levelno >= logging.ERROR
                else "WARNING"
            )
            category = getattr(record, "category", None)
            if not category:
                from services.monitoring import _route_error_category
                category = _route_error_category()
            record_error(
                category,
                level,
                record.getMessage(),
                status=None,
            )
        except Exception:
            # Logging must never change the response path.
            pass
        finally:
            self._state.active = False


def configure_logging(app):
    """Install safe JSON stdout logging and optional local rotating logs."""
    app.logger.handlers.clear()
    app.logger.propagate = False
    app.logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(SafeJsonFormatter())
    handler.addFilter(RequestContextFilter())
    app.logger.addHandler(handler)

    event_handler = MonitoringEventHandler()
    event_handler.addFilter(RequestContextFilter())
    app.logger.addHandler(event_handler)

    if app.config.get("IS_PRODUCTION") or app.config.get("IS_VERCEL_RUNTIME"):
        return

    log_path = app.config.get("LOCAL_LOG_PATH")
    if not log_path:
        return

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rotating = TimedRotatingFileHandler(
        path,
        when="midnight",
        interval=1,
        backupCount=int(app.config.get("MONITORING_RETENTION_DAYS", 90)),
        encoding="utf-8",
    )
    rotating.setFormatter(SafeJsonFormatter())
    rotating.addFilter(RequestContextFilter())
    app.logger.addHandler(rotating)
