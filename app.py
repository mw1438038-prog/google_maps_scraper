
from io import BytesIO, StringIO
from copy import copy
import csv
import requests

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response,
    send_file,
)

from openpyxl import Workbook

from config import Config
from services.google_places import GooglePlacesService


# =========================================================
# COUNTRIES / CITIES API
# =========================================================

COUNTRIES_API_URL = (
    "https://countriesnow.space/api/v0.1/countries"
)

CITIES_API_URL = (
    "https://countriesnow.space/api/v0.1/countries/cities"
)


# =========================================================
# CREATE APP
# =========================================================

def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    # =====================================================
    # GOOGLE MAPS API KEY
    # =====================================================

    if not app.config["GOOGLE_MAPS_API_KEY"]:

        raise RuntimeError(
            "GOOGLE_MAPS_API_KEY is missing from .env"
        )

    google_places = GooglePlacesService(
        app.config["GOOGLE_MAPS_API_KEY"]
    )

    # =====================================================
    # HOME PAGE
    # =====================================================

    @app.route("/")
    def home():

        return render_template(
            "home.html"
        )

    # =====================================================
    # LEAD FINDER PAGE
    # =====================================================

    @app.route("/leads")
    def leads():

        return render_template(
            "index.html"
        )

    # =====================================================
    # GET COUNTRIES
    # =====================================================

    @app.route(
        "/api/countries",
        methods=["GET"]
    )
    def get_countries():

        try:

            response = requests.get(
                COUNTRIES_API_URL,
                timeout=20,
            )

            response.raise_for_status()

            data = response.json()

            countries = []

            for country in data.get(
                "data",
                []
            ):

                name = country.get(
                    "country",
                    ""
                ).strip()

                if name:

                    countries.append(
                        name
                    )

            countries = sorted(
                set(countries)
            )

            return jsonify({

                "success": True,

                "countries": countries,

            })

        except Exception as error:

            return jsonify({

                "success": False,

                "message":
                    "Could not load countries: "
                    + str(error),

            }), 500

    # =====================================================
    # GET CITIES
    # =====================================================

    @app.route(
        "/api/cities",
        methods=["POST"]
    )
    def get_cities():

        data = request.get_json(
            silent=True
        ) or {}

        country = data.get(
            "country",
            ""
        ).strip()

        if not country:

            return jsonify({

                "success": False,

                "message":
                    "Country is required.",

            }), 400

        try:

            response = requests.post(

                CITIES_API_URL,

                json={
                    "country": country
                },

                timeout=20,
            )

            response.raise_for_status()

            data = response.json()

            cities = data.get(
                "data",
                []
            )

            cities = [

                city.strip()

                for city in cities

                if isinstance(
                    city,
                    str
                )

                and city.strip()

            ]

            cities = sorted(
                set(cities)
            )

            return jsonify({

                "success": True,

                "country": country,

                "cities": cities,

            })

        except Exception as error:

            return jsonify({

                "success": False,

                "message":
                    "Could not load cities: "
                    + str(error),

            }), 500

    # =====================================================
    # SEARCH GOOGLE MAPS
    # =====================================================

    @app.route(
        "/api/search",
        methods=["POST"]
    )
    def search():

        data = request.get_json(
            silent=True
        ) or {}

        country = data.get(
            "country",
            ""
        ).strip()

        city = data.get(
            "city",
            ""
        ).strip()

        keyword = data.get(
            "keyword",
            ""
        ).strip()

        # =================================================
        # VALIDATION
        # =================================================

        if not country:

            return jsonify({

                "success": False,

                "message":
                    "Country is required.",

            }), 400

        if not city:

            return jsonify({

                "success": False,

                "message":
                    "City is required.",

            }), 400

        if not keyword:

            return jsonify({

                "success": False,

                "message":
                    "Keyword is required.",

            }), 400

        # =================================================
        # GOOGLE PLACES SEARCH
        # =================================================

        try:

            results = (
                google_places.search_places(
                    country=country,
                    city=city,
                    keyword=keyword,
                )
            )

            return jsonify({

                "success": True,

                "count": len(results),

                "results": results,

            })

        except Exception as error:

            return jsonify({

                "success": False,

                "message": str(error),

            }), 500

    # =====================================================
    # EXPORT CSV
    # =====================================================

    @app.route(
        "/api/export/csv",
        methods=["POST"]
    )
    def export_csv():

        data = request.get_json(
            silent=True
        ) or {}

        results = data.get(
            "results",
            []
        )

        # =================================================
        # VALIDATION
        # =================================================

        if not results:

            return jsonify({

                "success": False,

                "message":
                    "No leads available to export.",

            }), 400

        # =================================================
        # CREATE CSV IN MEMORY
        # =================================================

        output = StringIO(
            newline=""
        )

        # UTF-8 BOM
        # Excel ke liye useful hai

        output.write(
            "\ufeff"
        )

        writer = csv.writer(
            output,
            lineterminator="\n"
        )

        # =================================================
        # CSV HEADERS
        # =================================================

        writer.writerow([

            "Business Name",

            "Phone",

            "Website",

            "Location",

            "Rating",

            "Reviews",

            "Google Maps",

            "Types",

        ])

        # =================================================
        # CSV DATA
        # =================================================

        for place in results:

            writer.writerow([

                place.get(
                    "name",
                    ""
                ),

                place.get(
                    "phone",
                    ""
                ),

                place.get(
                    "website",
                    ""
                ),

                place.get(
                    "address",
                    ""
                ),

                place.get(
                    "rating",
                    ""
                ),

                place.get(
                    "reviews",
                    ""
                ),

                place.get(
                    "maps_url",
                    ""
                ),

                place.get(
                    "types",
                    ""
                ),

            ])

        csv_data = output.getvalue()

        output.close()

        # =================================================
        # SEND CSV
        # =================================================

        return Response(

            csv_data,

            mimetype=(
                "text/csv; charset=utf-8"
            ),

            headers={

                "Content-Disposition":
                    "attachment; "
                    "filename="
                    "google_maps_leads.csv"

            },

        )

    # =====================================================
    # EXPORT EXCEL
    # =====================================================

    @app.route(
        "/api/export/excel",
        methods=["POST"]
    )
    def export_excel():

        data = request.get_json(
            silent=True
        ) or {}

        results = data.get(
            "results",
            []
        )

        # =================================================
        # VALIDATION
        # =================================================

        if not results:

            return jsonify({

                "success": False,

                "message":
                    "No leads available to export.",

            }), 400

        # =================================================
        # CREATE WORKBOOK
        # =================================================

        workbook = Workbook()

        worksheet = workbook.active

        worksheet.title = (
            "Google Maps Leads"
        )

        # =================================================
        # HEADERS
        # =================================================

        headers = [

            "Business Name",

            "Phone",

            "Website",

            "Location",

            "Rating",

            "Reviews",

            "Google Maps",

            "Types",

        ]

        worksheet.append(
            headers
        )

        # =================================================
        # DATA
        # =================================================

        for place in results:

            worksheet.append([

                place.get(
                    "name",
                    ""
                ),

                place.get(
                    "phone",
                    ""
                ),

                place.get(
                    "website",
                    ""
                ),

                place.get(
                    "address",
                    ""
                ),

                place.get(
                    "rating",
                    ""
                ),

                place.get(
                    "reviews",
                    ""
                ),

                place.get(
                    "maps_url",
                    ""
                ),

                place.get(
                    "types",
                    ""
                ),

            ])

        # =================================================
        # COLUMN WIDTHS
        # =================================================

        column_widths = {

            "A": 40,

            "B": 20,

            "C": 45,

            "D": 70,

            "E": 12,

            "F": 12,

            "G": 60,

            "H": 40,

        }

        for column, width in (
            column_widths.items()
        ):

            worksheet.column_dimensions[
                column
            ].width = width

        # =================================================
        # HEADER BOLD
        # =================================================

        for cell in worksheet[1]:

            font = copy(
                cell.font
            )

            font.bold = True

            cell.font = font

        # =================================================
        # FREEZE HEADER
        # =================================================

        worksheet.freeze_panes = (
            "A2"
        )

        # =================================================
        # SAVE EXCEL TO MEMORY
        # =================================================

        output = BytesIO()

        workbook.save(
            output
        )

        output.seek(0)

        # =================================================
        # SEND EXCEL
        # =================================================

        return send_file(

            output,

            as_attachment=True,

            download_name=(
                "google_maps_leads.xlsx"
            ),

            mimetype=(
                "application/"
                "vnd.openxmlformats-"
                "officedocument."
                "spreadsheetml.sheet"
            ),

        )

    # =====================================================
    # RETURN APP
    # =====================================================

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
