from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
)

from services.google_places import (
    GooglePlacesService,
)

from services.website_scraper import (
    WebsiteScraper,
)

from routes.pagination import (
    paginate_results,
)

from routes.search_cache import (
    save_search,
    get_search,
)


# =====================================================
# BLUEPRINT
# =====================================================

search_bp = Blueprint(
    "search",
    __name__,
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


    if not website:

        return place


    try:

        scraped_data = (
            website_scraper.scrape(
                website
            )
        )


        if scraped_data:

            place.update(
                scraped_data
            )


    except Exception:

        pass


    return place


# =====================================================
# SCRAPE ALL WEBSITES
# =====================================================

def scrape_results(results):

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


    # =================================================
    # EMPTY SOCIAL FIELDS
    # =================================================

    for place in places_without_websites:

        place["email"] = ""
        place["facebook"] = ""
        place["instagram"] = ""
        place["linkedin"] = ""
        place["twitter"] = ""
        place["other_social"] = ""


    # =================================================
    # SCRAPE WEBSITES
    # =================================================

    scraped_results = []


    if places_with_websites:

        with ThreadPoolExecutor(
            max_workers=10
        ) as executor:

            futures = [

                executor.submit(
                    scrape_one_website,
                    place
                )

                for place
                in places_with_websites

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
    # MAP SCRAPED RESULTS
    # =================================================

    result_map = {

        place.get("id"):
            place

        for place
        in scraped_results

    }


    # =================================================
    # FINAL RESULTS
    # =================================================

    final_results = []


    for place in results:

        place_id = place.get(
            "id"
        )


        if place_id in result_map:

            final_results.append(
                result_map[
                    place_id
                ]
            )

        else:

            final_results.append(
                place
            )


    return final_results


# =====================================================
# GET PAGINATED RESULTS
# =====================================================

def get_page_results(
    results,
    page
):

    return paginate_results(

        results,

        page=page,

        per_page=15

    )


# =====================================================
# NEW SEARCH
#
# Google API is called ONLY here.
# =====================================================

@search_bp.route(
    "/api/search",
    methods=["POST"]
)
def search():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    # =================================================
    # INPUT
    # =================================================

    country = str(
        data.get(
            "country",
            ""
        )
    ).strip()


    city = str(
        data.get(
            "city",
            ""
        )
    ).strip()


    keyword = str(
        data.get(
            "keyword",
            ""
        )
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


    try:

        # =============================================
        # GOOGLE PLACES
        #
        # THIS RUNS ONLY FOR NEW SEARCH
        # =============================================

        google_places = (
            GooglePlacesService(

                current_app.config[
                    "GOOGLE_MAPS_API_KEY"
                ]

            )
        )


        search_data = (
            google_places.search_places(

                country=country,

                city=city,

                keyword=keyword,

            )
        )


        # =============================================
        # GOOGLE RESULTS
        # =============================================

        results = (
            search_data.get(
                "results",
                []
            )
        )


        print(
            f"[SEARCH] Google results: "
            f"{len(results)}"
        )


        # =============================================
        # WEBSITE SCRAPING
        #
        # ALSO ONLY RUNS FOR NEW SEARCH
        # =============================================

        final_results = (
            scrape_results(
                results
            )
        )


        print(
            f"[SEARCH] Final results: "
            f"{len(final_results)}"
        )


        # =============================================
        # SAVE COMPLETE SEARCH
        # =============================================

        search_id = save_search(

            results=final_results,

            country=country,

            city=city,

            keyword=keyword,

        )


        print(
            f"[SEARCH] Search ID: "
            f"{search_id}"
        )


        # =============================================
        # FIRST PAGE
        # =============================================

        pagination_data = (
            get_page_results(

                results=final_results,

                page=1

            )
        )


        # =============================================
        # RETURN
        # =============================================

        return jsonify({

            "success":
                True,

            "search_id":
                search_id,

            "count":
                len(
                    pagination_data[
                        "results"
                    ]
                ),

            "results":
                pagination_data[
                    "results"
                ],

            "pagination":
                pagination_data[
                    "pagination"
                ],

            "search_query":
                search_data.get(
                    "search_query",
                    ""
                ),

        })


    except Exception as error:

        print(
            "[SEARCH ERROR]",
            error
        )


        return jsonify({

            "success":
                False,

            "message":
                str(error),

        }), 500


# =====================================================
# PAGINATION PAGE
#
# IMPORTANT:
# Google API is NOT called here.
# Website scraper is NOT called here.
#
# Saved cache is used.
# =====================================================

@search_bp.route(
    "/api/search/page",
    methods=["POST"]
)
def search_page():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    # =================================================
    # SEARCH ID
    # =================================================

    search_id = str(
        data.get(
            "search_id",
            ""
        )
    ).strip()


    # =================================================
    # PAGE
    # =================================================

    page = data.get(
        "page",
        1
    )


    try:

        page = int(
            page
        )

    except (
        TypeError,
        ValueError
    ):

        page = 1


    if page < 1:

        page = 1


    # =================================================
    # VALIDATE SEARCH ID
    # =================================================

    if not search_id:

        return jsonify({

            "success":
                False,

            "message":
                "Search session has expired. "
                "Please perform a new search.",

        }), 400


    # =================================================
    # GET CACHED SEARCH
    # =================================================

    search_data = get_search(
        search_id
    )


    if not search_data:

        return jsonify({

            "success":
                False,

            "message":
                "Search session has expired. "
                "Please perform a new search.",

        }), 404


    # =================================================
    # GET SAVED RESULTS
    # =================================================

    results = search_data.get(
        "results",
        []
    )


    # =================================================
    # PAGINATE SAVED RESULTS
    # =================================================

    pagination_data = (
        get_page_results(

            results=results,

            page=page

        )
    )


    pagination = (
        pagination_data[
            "pagination"
        ]
    )


    page_results = (
        pagination_data[
            "results"
        ]
    )


    print(
        f"[PAGINATION] "
        f"Search ID: {search_id} | "
        f"Page: {pagination['page']} | "
        f"Total: {pagination['total']}"
    )


    # =================================================
    # RETURN
    # =================================================

    return jsonify({

        "success":
            True,

        "search_id":
            search_id,

        "count":
            len(
                page_results
            ),

        "results":
            page_results,

        "pagination":
            pagination,

        "search_query":
            (
                f"{search_data.get('keyword', '')} "
                f"in {search_data.get('city', '')}, "
                f"{search_data.get('country', '')}"
            ),

    })