
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

from routes.usage import (
    get_current_user,
    can_search,
    consume_search,
    get_usage,
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
# APP PAGINATION
#
# Always 15 results per page.
#
# Completely separate from Google API pagination.
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
# SEARCH LIMIT / SUBSCRIPTION MESSAGE
# =====================================================

def get_limit_message(user):

    plan = (
        user.plan or "free"
    ).lower().strip()

    subscription_status = (
        user.subscription_status
        or "inactive"
    ).lower().strip()

    # =================================================
    # EXPIRED PAID SUBSCRIPTION
    # =================================================

    if (
        plan in (
            "pro",
            "business",
        )
        and subscription_status == "expired"
    ):

        plan_name = (
            "Pro"
            if plan == "pro"
            else "Business"
        )

        return (
            f"Your {plan_name} subscription "
            "has expired. Please renew your "
            "subscription to continue searching."
        )

    # =================================================
    # FREE PLAN
    # =================================================

    if plan == "free":

        return (
            "Your 10 Free searches have "
            "been used. Your Free trial is "
            "available only once. Please "
            "upgrade to Pro or Business."
        )

    # =================================================
    # PRO SEARCH LIMIT
    # =================================================

    if plan == "pro":

        return (
            "You have reached your monthly "
            "Pro search limit. Please wait "
            "for your next billing cycle "
            "or upgrade your plan."
        )

    # =================================================
    # BUSINESS SEARCH LIMIT
    # =================================================

    if plan == "business":

        return (
            "You have reached your monthly "
            "Business search limit. Please "
            "wait for your next billing cycle."
        )

    # =================================================
    # DEFAULT
    # =================================================

    return (
        "You have reached your search limit."
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

    # =================================================
    # CURRENT USER
    # =================================================

    user = get_current_user()

    if not user:

        return jsonify({

            "success": False,

            "message":
                "Please login before searching.",

        }), 401

    # =================================================
    # CHECK SEARCH / SUBSCRIPTION LIMIT
    #
    # IMPORTANT:
    #
    # This happens BEFORE Google API.
    #
    # Therefore:
    #
    # - expired Pro = no Google API
    # - expired Business = no Google API
    # - exhausted Free = no Google API
    # - exhausted Pro = no Google API
    # - exhausted Business = no Google API
    # =================================================

    if not can_search(user):

        return jsonify({

            "success": False,

            "message":
                get_limit_message(user),

            "usage":
                get_usage(user),

        }), 403

    # =================================================
    # INPUT
    # =================================================

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

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
        # GOOGLE PLACES SERVICE
        # =============================================

        google_places = (
            GooglePlacesService(

                current_app.config[
                    "GOOGLE_MAPS_API_KEY"
                ]

            )
        )

        # =============================================
        # USER PLAN
        # =============================================

        user_plan = (
            user.plan or "free"
        ).lower().strip()

        # =============================================
        # GOOGLE SEARCH
        #
        # Plan limits:
        #
        # Free     = 15
        # Pro      = 100
        # Business = 200
        # =============================================

        search_data = (
            google_places.search_places(

                country=country,

                city=city,

                keyword=keyword,

                plan=user_plan,

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
        # GET PLAN RESULT LIMIT
        # =============================================

        usage = get_usage(
            user
        )

        results_limit = usage.get(
            "results_per_search",
            15
        )

        # =============================================
        # APPLY PLAN RESULT LIMIT
        # =============================================

        results = results[
            :results_limit
        ]

        print(
            f"[SEARCH] Plan: "
            f"{user_plan}"
        )

        print(
            f"[SEARCH] Plan result limit: "
            f"{results_limit}"
        )

        print(
            f"[SEARCH] Results after plan limit: "
            f"{len(results)}"
        )

        # =============================================
        # WEBSITE SCRAPING
        #
        # Only plan-limited results are scraped.
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
        # CONSUME ONE SEARCH
        #
        # Only successful NEW searches consume
        # one search credit.
        # =============================================

        if not consume_search(
            user
        ):

            return jsonify({

                "success": False,

                "message":
                    get_limit_message(user),

                "usage":
                    get_usage(user),

            }), 403

        # =============================================
        # SAVE SEARCH IN CACHE
        #
        # Google Maps results are NOT stored in
        # PostgreSQL.
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
        # FIRST APP PAGE
        #
        # Always 15 results.
        # =============================================

        pagination_data = (
            get_page_results(

                results=final_results,

                page=1

            )
        )

        # =============================================
        # CURRENT USAGE
        # =============================================

        usage = get_usage(
            user
        )

        # =============================================
        # RETURN
        # =============================================

        return jsonify({

            "success": True,

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

            "usage":
                usage,

        })

    except Exception as error:

        print(
            "[SEARCH ERROR]",
            error
        )

        return jsonify({

            "success": False,

            "message":
                str(error),

        }), 500


# =====================================================
# PAGINATION PAGE
#
# IMPORTANT:
#
# Google API is NOT called.
#
# Website scraper is NOT called.
#
# Search credit is NOT consumed.
#
# Cached results are used.
# =====================================================

@search_bp.route(
    "/api/search/page",
    methods=["POST"]
)
def search_page():

    # =================================================
    # INPUT
    # =================================================

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

            "success": False,

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

            "success": False,

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
    # APP PAGINATION
    #
    # Always 15 results per page.
    #
    # Google API is NOT called.
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

    # =================================================
    # DEBUG
    # =================================================

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

        "success": True,

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

