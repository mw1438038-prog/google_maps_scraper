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
    # FLASK SESSION
    # =====================================================

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        ""
    )

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SAMESITE = "Lax"

    # HTTPS on Vercel
    SESSION_COOKIE_SECURE = (
        os.getenv("VERCEL") == "1"
    )