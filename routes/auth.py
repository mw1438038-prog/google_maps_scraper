from flask import (
    Blueprint,
    redirect,
    url_for,
    session,
)

from authlib.integrations.flask_client import OAuth

from extensions import db
from models.user import User


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


oauth = OAuth()


# =====================================================
# INITIALIZE GOOGLE OAUTH
# =====================================================

def init_oauth(app):

    oauth.init_app(app)

    oauth.register(
        name="google",

        client_id=app.config["GOOGLE_CLIENT_ID"],

        client_secret=app.config["GOOGLE_CLIENT_SECRET"],

        server_metadata_url=(
            "https://accounts.google.com/"
            ".well-known/openid-configuration"
        ),

        client_kwargs={
            "scope": "openid email profile"
        },
    )


# =====================================================
# GOOGLE LOGIN
# =====================================================

@auth_bp.route("/google")
def google_login():

    redirect_uri = url_for(
        "auth.google_callback",
        _external=True
    )

    return oauth.google.authorize_redirect(
        redirect_uri
    )


# =====================================================
# GOOGLE CALLBACK
# =====================================================

@auth_bp.route("/google/callback")
def google_callback():

    # -------------------------------------------------
    # GET GOOGLE TOKEN
    # -------------------------------------------------

    token = oauth.google.authorize_access_token()

    # -------------------------------------------------
    # GET USER INFO
    # -------------------------------------------------

    user_info = token.get("userinfo")

    if not user_info:
        user_info = oauth.google.userinfo()

    google_id = user_info.get("sub")
    name = user_info.get("name")
    email = user_info.get("email")
    picture = user_info.get("picture")

    # -------------------------------------------------
    # VALIDATE GOOGLE DATA
    # -------------------------------------------------

    if not google_id or not email:

        return (
            "Google account information is incomplete.",
            400
        )

    # =================================================
    # FIND USER IN DATABASE
    # =================================================

    user = User.query.filter_by(
        google_id=google_id
    ).first()

    # =================================================
    # CREATE NEW USER
    # =================================================

    if not user:

        user = User(
            google_id=google_id,
            name=name,
            email=email,
            picture=picture,
            plan="free",
        )

        db.session.add(user)

    # =================================================
    # UPDATE EXISTING USER
    # =================================================

    else:

        user.name = name
        user.email = email
        user.picture = picture

    # =================================================
    # SAVE DATABASE CHANGES
    # =================================================

    db.session.commit()

    # =================================================
    # FLASK SESSION
    # =================================================

    session["user"] = {
        "id": user.id,
        "google_id": user.google_id,
        "name": user.name,
        "email": user.email,
        "picture": user.picture,
        "plan": user.plan,
    }

    session.permanent = True

    # =================================================
    # DASHBOARD
    # =================================================

    return redirect(
        url_for("leads")
    )


# =====================================================
# LOGOUT
# =====================================================

@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )