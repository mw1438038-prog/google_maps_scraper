
from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
    request,
)

from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config, validate_production_config
from extensions import db
from services.database_startup import initialize_database
from services.logging_config import configure_logging

# Register models before database initialization
from models.user import User
from models.exported_lead import ExportedLead
from models.freemius_webhook_event import FreemiusWebhookEvent
from models.error_event import ErrorEvent
from models.request_metric import RequestMetric
from models.component_health import ComponentHealth

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
from services.monitoring import initialize_request_tracking


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    validate_production_config(app.config)
    configure_logging(app)

    # Database
    db.init_app(app)

    try:
        initialize_database(app)
        app.logger.info("Database schema check completed successfully.")

    except Exception as error:
        # Preserve the original failure; startup has no active session to roll back.
        app.logger.exception(
            "Database initialization or schema check failed (%s): %s",
            type(error).__name__,
            error,
            extra={
                "category": "neon",
                "monitoring_exception_type": type(error).__name__,
            },
        )
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

    initialize_request_tracking(app)

    @app.before_request
    def validate_user_session():
        # Public routes remain accessible without login.
        public_endpoints = {
            "home",
            "pricing_page",
            "privacy_policy",
            "auth.google_login",
            "auth.google_callback",
            "static",
        }

        if request.endpoint in public_endpoints or request.endpoint is None:
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
            app.logger.exception(
                "Could not validate the logged-in user.",
                extra={
                    "category": "neon",
                    "monitoring_exception_type": "DatabaseQueryError",
                },
            )
            session.clear()
            return redirect(url_for("home"))

        return None

    # Home
    @app.route("/")
    def home():
        return render_template("home.html")

    # Privacy Policy
    @app.route("/privacy-policy")
    def privacy_policy():
        return render_template("privacy_policy.html")

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
