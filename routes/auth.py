from flask import (
    Blueprint,
    redirect,
    url_for,
    session,
)

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import MismatchingStateError

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

    # Start a fresh OAuth flow.
    session.permanent = True

    redirect_uri = url_for(
        "auth.google_callback",
        _external=True
    )

    return oauth.google.authorize_redirect(
        redirect_uri=redirect_uri
    )


# =====================================================
# GOOGLE CALLBACK
# =====================================================

@auth_bp.route("/google/callback")
def google_callback():

    # -------------------------------------------------
    # VERIFY GOOGLE OAUTH STATE
    # -------------------------------------------------

    try:

        token = oauth.google.authorize_access_token()

    except MismatchingStateError:

        # -------------------------------------------------
        # IMPORTANT:
        # Do NOT disable Authlib state validation.
        #
        # This can happen when the browser comes back to
        # an old OAuth callback from browser history.
        #
        # Start a completely fresh OAuth flow instead.
        # -------------------------------------------------

        session.clear()

        return redirect(
            url_for("auth.google_login")
        )

    # -------------------------------------------------
    # GET USER INFO
    # -------------------------------------------------

    user_info = token.get("userinfo")

    if not user_info:
        user_info = oauth.google.userinfo()

    if not user_info:

        return (
            "Unable to get Google account information.",
            400
        )

    # -------------------------------------------------
    # GOOGLE USER DATA
    # -------------------------------------------------

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
    # FIND USER
    # =================================================

    user = User.query.filter_by(
        google_id=google_id
    ).first()

    # =================================================
    # CREATE USER
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
    # SAVE DATABASE
    # =================================================

    db.session.commit()

    # =================================================
    # CREATE APPLICATION SESSION
    # =================================================

    session.clear()

    session.permanent = True

    session["user"] = {
        "id": user.id,
        "google_id": user.google_id,
        "name": user.name,
        "email": user.email,
        "picture": user.picture,
        "plan": user.plan,
    }

    # =================================================
    # REDIRECT TO PROFILE
    # =================================================

    return redirect(
        url_for("profile.profile")
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