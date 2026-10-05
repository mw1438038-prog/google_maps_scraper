from io import BytesIO, StringIO
from copy import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv

import geonamescache

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
from services.website_scraper import WebsiteScraper


# =========================================================
# GEONAMES CACHE
# =========================================================

gc = geonamescache.GeonamesCache()


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
    # WEBSITE SCRAPER
    # =====================================================

    website_scraper = WebsiteScraper(
        timeout=5
    )

    # =====================================================
    # SCRAPE ONE WEBSITE
    # =====================================================

    def scrape_one_website(place):

        # -------------------------------------------------
        # DEFAULT EMPTY FIELDS
        # -------------------------------------------------

        place["email"] = ""
        place["facebook"] = ""
        place["instagram"] = ""
        place["linkedin"] = ""
        place["twitter"] = ""
        place["other_social"] = ""

        website = place.get(
            "website",
            ""
        )

        # -------------------------------------------------
        # NO WEBSITE
        # -------------------------------------------------

        if not website:
            return place

        # -------------------------------------------------
        # SCRAPE WEBSITE
        # -------------------------------------------------

        try:

            scraped_data = (
                website_scraper.scrape(
                    website
                )
            )

            place.update(
                scraped_data
            )

        except Exception:

            # One website failure should
            # not stop the complete search.

            pass

        return place

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
    #
    # CountriesNow API removed.
    # Countries are loaded locally from geonamescache.
    # =====================================================

    @app.route(
        "/api/countries",
        methods=["GET"]
    )
    def get_countries():

        try:

            countries_data = (
                gc.get_countries()
            )

            countries = []

            for country in countries_data.values():

                name = country.get(
                    "name",
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
    #
    # Cities are loaded locally from geonamescache.
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

            # =============================================
            # FIND COUNTRY CODE
            # =============================================

            countries_data = (
                gc.get_countries()
            )

            country_code = None

            for code, country_data in (
                countries_data.items()
            ):

                country_name = country_data.get(
                    "name",
                    ""
                ).strip()

                if (
                    country_name.lower()
                    == country.lower()
                ):

                    country_code = code

                    break

            # =============================================
            # COUNTRY NOT FOUND
            # =============================================

            if not country_code:

                return jsonify({

                    "success": False,

                    "message":
                        "Country not found.",

                }), 404

            # =============================================
            # GET CITIES
            # =============================================

            cities_data = (
                gc.get_cities()
            )

            cities = []

            for city_data in (
                cities_data.values()
            ):

                city_country_code = (
                    city_data.get(
                        "countrycode",
                        ""
                    )
                )

                if (
                    city_country_code
                    == country_code
                ):

                    city_name = city_data.get(
                        "name",
                        ""
                    ).strip()

                    if city_name:

                        cities.append(
                            city_name
                        )

            # =============================================
            # REMOVE DUPLICATES
            # =============================================

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
    # SEARCH GOOGLE MAPS + WEBSITE SCRAPER
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

            # =================================================
            # PARALLEL WEBSITE SCRAPING
            # =================================================

            scraped_results = []

            # Only submit places that actually
            # have a website.

            places_with_websites = [
                place
                for place in results
                if place.get(
                    "website",
                    ""
                )
            ]

            places_without_websites = [
                place
                for place in results
                if not place.get(
                    "website",
                    ""
                )
            ]

            # -------------------------------------------------
            # DEFAULT FIELDS FOR PLACES WITHOUT WEBSITE
            # -------------------------------------------------

            for place in places_without_websites:

                place["email"] = ""
                place["facebook"] = ""
                place["instagram"] = ""
                place["linkedin"] = ""
                place["twitter"] = ""
                place["other_social"] = ""

            # -------------------------------------------------
            # SCRAPE UP TO 10 WEBSITES AT THE SAME TIME
            # -------------------------------------------------

            if places_with_websites:

                with ThreadPoolExecutor(
                    max_workers=10
                ) as executor:

                    futures = [
                        executor.submit(
                            scrape_one_website,
                            place
                        )
                        for place in places_with_websites
                    ]

                    for future in as_completed(
                        futures
                    ):

                        try:

                            scraped_place = (
                                future.result()
                            )

                            scraped_results.append(
                                scraped_place
                            )

                        except Exception:

                            continue

            # =================================================
            # KEEP ORIGINAL GOOGLE RESULTS ORDER
            # =================================================

            result_map = {
                place.get("id"): place
                for place in scraped_results
            }

            final_results = []

            for place in results:

                place_id = place.get(
                    "id"
                )

                if place_id in result_map:

                    final_results.append(
                        result_map[place_id]
                    )

                else:

                    final_results.append(
                        place
                    )

            results = final_results

            # =================================================
            # RETURN RESULTS
            # =================================================

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

        if not results:

            return jsonify({

                "success": False,

                "message":
                    "No leads available to export.",

            }), 400

        # =================================================
        # CREATE CSV
        # =================================================

        output = StringIO(
            newline=""
        )

        # UTF-8 BOM for Excel
        output.write(
            "\ufeff"
        )

        writer = csv.writer(
            output,
            lineterminator="\n"
        )

        # =================================================
        # HEADERS
        # =================================================

        writer.writerow([

            "Business Name",

            "Phone",

            "Website",

            "Email",

            "Facebook",

            "Instagram",

            "LinkedIn",

            "Twitter",

            "Other Social",

            "Location",

            "Rating",

            "Reviews",

            "Google Maps",

            "Types",

        ])

        # =================================================
        # DATA
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
                    "email",
                    ""
                ),

                place.get(
                    "facebook",
                    ""
                ),

                place.get(
                    "instagram",
                    ""
                ),

                place.get(
                    "linkedin",
                    ""
                ),

                place.get(
                    "twitter",
                    ""
                ),

                place.get(
                    "other_social",
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

        worksheet = (
            workbook.active
        )

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

            "Email",

            "Facebook",

            "Instagram",

            "LinkedIn",

            "Twitter",

            "Other Social",

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
                    "email",
                    ""
                ),

                place.get(
                    "facebook",
                    ""
                ),

                place.get(
                    "instagram",
                    ""
                ),

                place.get(
                    "linkedin",
                    ""
                ),

                place.get(
                    "twitter",
                    ""
                ),

                place.get(
                    "other_social",
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

            "D": 35,

            "E": 45,

            "F": 45,

            "G": 45,

            "H": 45,

            "I": 60,

            "J": 70,

            "K": 12,

            "L": 12,

            "M": 60,

            "N": 40,

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