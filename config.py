
import os

from dotenv import load_dotenv

load_dotenv()


class Config:

    # =====================================================
    # GOOGLE MAPS
    # =====================================================

    GOOGLE_MAPS_API_KEY = os.getenv(
        "GOOGLE_MAPS_API_KEY",
        ""
    )

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

    FREEMIUS_WEBHOOK_ID = os.getenv(
        "FREEMIUS_WEBHOOK_ID",
        ""
    )

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
