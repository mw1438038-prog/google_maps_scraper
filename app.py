from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
)

from config import Config

from routes.locations import locations_bp
from routes.search import search_bp
from routes.export import export_bp

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
        auth_bp
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
    # LEADS PAGE
    # =====================================================

    @app.route("/leads")
    def leads():

        # User must be logged in
        if "user" not in session:

            return redirect(
                url_for(
                    "auth.google_login"
                )
            )

        return render_template(
            "index.html"
        )

    return app


app = create_app()


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )