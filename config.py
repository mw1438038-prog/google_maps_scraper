
import os

from dotenv import load_dotenv

load_dotenv()


def _int_setting(name, default, minimum=1):
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _bool_setting(name, default=True):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_vercel_production(environ=None):
    """Treat checkout as live only inside a marked Vercel Production runtime."""
    environ = os.environ if environ is None else environ
    return (
        environ.get("VERCEL", "") == "1"
        and environ.get("VERCEL_ENV", "").strip().lower() == "production"
    )


def is_vercel_runtime(environ=None):
    environ = os.environ if environ is None else environ
    return (
        environ.get("VERCEL", "") == "1"
        or environ.get("VERCEL_ENV", "").strip().lower()
        in {"production", "preview", "development"}
    )


def validate_production_config(config):
    if config.get("IS_PRODUCTION") and not str(
        config.get("SECRET_KEY") or ""
    ).strip():
        raise RuntimeError(
            "SECRET_KEY must be configured for Vercel Production."
        )


class Config:

    # =====================================================
    # APPLICATION MONITORING AND LOGGING
    # =====================================================

    MONITORING_RETENTION_DAYS = 90
    MONITORING_SLOW_REQUEST_MS = int(
        _int_setting("MONITORING_SLOW_REQUEST_MS", 2000)
    )
    LOCAL_LOG_PATH = os.getenv("LOCAL_LOG_PATH", "")

    # =====================================================
    # GOOGLE MAPS
    # =====================================================

    GOOGLE_MAPS_API_KEY = os.getenv(
        "GOOGLE_MAPS_API_KEY",
        ""
    )
    GOOGLE_MAPS_ENABLED = _bool_setting("GOOGLE_MAPS_ENABLED")

    # =====================================================
    # GOOGLE LOGIN
    # =====================================================

    GOOGLE_CLIENT_ID = os.getenv(
        "GOOGLE_CLIENT_ID",
        ""
    )

    GOOGLE_CLIENT_SECRET = os.getenv(
        "GOOGLE_CLIENT_SECRET",
        ""
    )

    # =====================================================
    # FREEMIUS PAYMENTS
    # =====================================================

    FREEMIUS_PRODUCT_ID = os.getenv(
        "FREEMIUS_PRODUCT_ID",
        ""
    )

    FREEMIUS_PRO_PLAN_ID = os.getenv(
        "FREEMIUS_PRO_PLAN_ID",
        ""
    )

    FREEMIUS_BUSINESS_PLAN_ID = os.getenv(
        "FREEMIUS_BUSINESS_PLAN_ID",
        ""
    )

    FREEMIUS_API_BEARER_TOKEN = os.getenv(
        "FREEMIUS_API_BEARER_TOKEN",
        ""
    )

    FREEMIUS_PRODUCT_SECRET_KEY = os.getenv(
        "FREEMIUS_PRODUCT_SECRET_KEY",
        ""
    )

    FREEMIUS_PUBLIC_KEY = os.getenv(
        "FREEMIUS_PUBLIC_KEY",
        ""
    )

    FREEMIUS_WEBHOOK_ID = os.getenv(
        "FREEMIUS_WEBHOOK_ID",
        ""
    )

    # Missing Vercel runtime markers fail closed to sandbox mode.
    IS_VERCEL_RUNTIME = is_vercel_runtime()
    IS_PRODUCTION = is_vercel_production()
    FREEMIUS_SANDBOX = not IS_PRODUCTION

    # =====================================================
    # DATABASE
    # =====================================================

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        ""
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 30,
        "connect_args": {
        "connect_timeout": 10,
    },
}

    # =====================================================
    # FLASK SESSION
    # =====================================================

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        ""
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_SECURE = (
        os.getenv("VERCEL") == "1"
    )

    SESSION_PERMANENT = True
    SESSION_COOKIE_PATH = "/"
