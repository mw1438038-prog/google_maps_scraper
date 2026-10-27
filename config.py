
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
    # DATABASE
    # =====================================================

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        ""
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
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
