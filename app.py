
import logging

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
)

from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import db

# Register models before database initialization
from models.user import User
from models.exported_lead import ExportedLead

# Blueprints
from routes.locations import locations_bp
from routes.search import search_bp
from routes.export import export_bp
from routes.usage import usage_bp
from routes.plans import plans_bp
from routes.checkout import checkout_bp
from routes.payment import payment_bp

from routes.auth import auth_bp, init_oauth
from routes.profile import profile_bp


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Database
    db.init_app(app)

    # Create tables. If the database is unavailable, log the
    # actual error instead of hiding it.
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables verified successfully.")
        except Exception:
            db.session.rollback()
            logger.exception("Database initialization failed.")
            raise

    # Reverse proxy support
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
    )

    # Google OAuth
    init_oauth(app)

    # Blueprints
    app.register_blueprint(locations_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(profile_bp)

    @app.before_request
    def validate_user_session():
        # Public routes remain accessible without login.
        endpoint = __import__("flask").request.endpoint

        public_endpoints = {
            "home",
            "pricing_page",
            "auth.google_login",
            "auth.google_callback",
            "static",
        }

        if endpoint in public_endpoints or endpoint is None:
            return None

        user_data = session.get("user")

        # No session: let existing route/API authentication
        # rules handle the request.
        if not user_data:
            return None

        user_id = user_data.get("id")

        if not user_id:
            session.clear()
            return redirect(url_for("home"))

        try:
            user = db.session.get(User, user_id)

            if user is None:
                session.clear()
                return redirect(url_for("home"))

        except Exception:
            db.session.rollback()
            logger.exception("Could not validate the logged-in user.")
            session.clear()
            return redirect(url_for("home"))

        return None

    # Home
    @app.route("/")
    def home():
        return render_template("home.html")

    # Leads dashboard
    @app.route("/leads")
    def leads():
        user_data = session.get("user")

        if not user_data:
            return redirect(url_for("home"))

        return render_template("index.html")



    # Pricing
    @app.route("/pricing")
    def pricing_page():
        return render_template("pricing.html")
    
    # Subscription
    @app.route("/subscription")
    def subscription_page():
        user_data = session.get("user")

        if not user_data:
            return redirect(url_for("home"))

        return render_template("subscription.html")
    

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
