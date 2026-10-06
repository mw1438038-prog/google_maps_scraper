import geonamescache

from flask import (
    Blueprint,
    request,
    jsonify,
)


locations_bp = Blueprint(
    "locations",
    __name__,
)


gc = geonamescache.GeonamesCache()


@locations_bp.route(
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
                countries.append(name)

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


@locations_bp.route(
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

        if not country_code:

            return jsonify({

                "success": False,

                "message":
                    "Country not found.",

            }), 404

        cities_data = (
            gc.get_cities()
        )

        cities = []

        for city_data in (
            cities_data.values()
        ):

            if (
                city_data.get(
                    "countrycode",
                    ""
                )
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