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



from routes.locations import locations_bp
from routes.search import search_bp
from routes.export import export_bp
from routes.usage import usage_bp
from routes.plans import plans_bp
from routes.checkout import checkout_bp
from routes.payment import payment_bp

from routes.auth import (
    auth_bp,
    init_oauth,
)


def create_app():

    app = Flask(__name__)

    # =====================================================
    # CONFIG
    # =====================================================

    app.config.from_object(Config)


    # =====================================================
    # DATABASE
    # =====================================================

    db.init_app(app)

    with app.app_context():

        db.create_all()


    # =====================================================
    # PROXY
    # =====================================================

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
    )


    # =====================================================
    # GOOGLE OAUTH
    # =====================================================

    init_oauth(app)


    # =====================================================
    # BLUEPRINTS
    # =====================================================

    app.register_blueprint(
        locations_bp
    )

    app.register_blueprint(
        search_bp
    )

    app.register_blueprint(
        export_bp
    )

    app.register_blueprint(
        usage_bp
    )

    app.register_blueprint(
        plans_bp
    )

    app.register_blueprint(
        auth_bp
    )

    app.register_blueprint(
        checkout_bp
    )

    app.register_blueprint(
        payment_bp
    )

    # =====================================================
    # HOME
    # =====================================================

    @app.route("/")
    def home():

        return render_template(
            "home.html"
        )


    # =====================================================
    # LEADS DASHBOARD
    # =====================================================

    @app.route("/leads")
    def leads():

        if "user" not in session:

            return redirect(
                url_for(
                    "auth.google_login"
                )
            )

        return render_template(
            "index.html"
        )


    # =====================================================
    # PRICING
    # =====================================================

    @app.route("/pricing")
    def pricing_page():

        return render_template(
            "pricing.html"
        )


    return app


# =========================================================
# APP
# =========================================================

app = create_app()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )