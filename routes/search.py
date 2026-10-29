
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Blueprint, request, jsonify, current_app

from services.google_places import GooglePlacesService
from services.website_scraper import WebsiteScraper

from routes.pagination import paginate_results
from routes.search_cache import save_search, delete_search, get_search

from models.search_history import SearchHistory

from routes.usage import (
    get_current_user,
    can_search,
    consume_search,
    get_usage,
)


# =====================================================
# BLUEPRINT
# =====================================================

search_bp = Blueprint("search", __name__)


# =====================================================
# WEBSITE SCRAPER
# =====================================================

website_scraper = WebsiteScraper(timeout=5)


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

    website = place.get("website", "")

    if not website:
        return place

    try:
        scraped_data = website_scraper.scrape(website)

        if scraped_data:
            place.update(scraped_data)

    except Exception:
        current_app.logger.exception(
            "Website scraping failed for a result."
        )

    return place


# =====================================================
# SCRAPE ALL WEBSITES
# =====================================================

def scrape_results(results):
    places_with_websites = [
        place for place in results
        if place.get("website", "")
    ]

    places_without_websites = [
        place for place in results
        if not place.get("website", "")
    ]

    for place in places_without_websites:
        place["email"] = ""
        place["facebook"] = ""
        place["instagram"] = ""
        place["linkedin"] = ""
        place["twitter"] = ""
        place["other_social"] = ""

    scraped_results = []

    if places_with_websites:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(scrape_one_website, place)
                for place in places_with_websites
            ]

            for future in as_completed(futures):
                try:
                    scraped_results.append(future.result())
                except Exception:
                    current_app.logger.exception(
                        "A website scraping task failed."
                    )

    result_map = {
        place.get("id"): place
        for place in scraped_results
        if place.get("id")
    }

    final_results = []

    for place in results:
        place_id = place.get("id")

        if place_id and place_id in result_map:
            final_results.append(result_map[place_id])
        else:
            final_results.append(place)

    return final_results


# =====================================================
# APP PAGINATION
# 15 RESULTS PER PAGE
# This is display pagination, not a plan result limit.
# =====================================================

def get_page_results(results, page):
    return paginate_results(
        results,
        page=page,
        per_page=15,
    )


# =====================================================
# SEARCH LIMIT / SUBSCRIPTION MESSAGE
# =====================================================

def get_limit_message(user):
    plan = (user.plan or "free").lower().strip()

    subscription_status = (
        user.subscription_status or "inactive"
    ).lower().strip()

    if (
        plan in ("pro", "business")
        and subscription_status in ("expired", "cancelled")
    ):
        plan_name = "Pro" if plan == "pro" else "Business"

        return (
            f"Your {plan_name} subscription is no longer active. "
            "Please check your subscription to continue searching."
        )

    if plan == "free":
        return (
            "Your 10 Free searches have been used. "
            "Please upgrade to Pro or Business to continue."
        )

    if plan == "pro":
        return (
            "You have reached your monthly Pro search limit. "
            "Please wait for your next billing cycle or upgrade."
        )

    if plan == "business":
        return (
            "You have reached your monthly Business search limit. "
            "Please wait for your next billing cycle."
        )

    return "You have reached your search limit."


# =====================================================
# NEW SEARCH
# Google API is called only for a new search.
# =====================================================

@search_bp.route("/api/search", methods=["POST"])
def search():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please login before searching.",
        }), 401

    if not can_search(user):
        return jsonify({
            "success": False,
            "message": get_limit_message(user),
            "usage": get_usage(user),
        }), 403

    data = request.get_json(silent=True) or {}

    country = str(data.get("country", "")).strip()
    city = str(data.get("city", "")).strip()
    keyword = str(data.get("keyword", "")).strip()

    if not country:
        return jsonify({
            "success": False,
            "message": "Country is required.",
        }), 400

    if not city:
        return jsonify({
            "success": False,
            "message": "City is required.",
        }), 400

    if not keyword:
        return jsonify({
            "success": False,
            "message": "Keyword is required.",
        }), 400

    search_id = None

    try:
        api_key = current_app.config.get("GOOGLE_MAPS_API_KEY")

        if not api_key:
            current_app.logger.error(
                "Google Maps API key is not configured."
            )
            return jsonify({
                "success": False,
                "message": "Google Maps API is not configured.",
            }), 503

        google_places = GooglePlacesService(api_key)

        user_plan = (user.plan or "free").lower().strip()

        # Fetch all results Google makes available.
        # No Free/Pro/Business result slicing here.
        search_data = google_places.search_places(
            country=country,
            city=city,
            keyword=keyword,
            plan=user_plan,
        )

        results = search_data.get("results", [])

        current_app.logger.info(
            "Google Places returned %s results.",
            len(results),
        )

        # Scrape all returned results; no plan result limit.
        final_results = scrape_results(results)

        # Save the complete result set in cache.
        search_id = save_search(
            results=final_results,
            country=country,
            city=city,
            keyword=keyword,
        )

        history_record = SearchHistory(
            search_id=search_id,
            user_id=user.id,
            country=country,
            city=city,
            keyword=keyword,
            result_count=len(final_results),
            results=[],
        )

        # Consume one search credit for a successful new search.
        if not consume_search(user, history_record):
            delete_search(search_id)

            return jsonify({
                "success": False,
                "message": get_limit_message(user),
                "usage": get_usage(user),
            }), 403

        pagination_data = get_page_results(
            results=final_results,
            page=1,
        )

        usage = get_usage(user)

        return jsonify({
            "success": True,
            "search_id": search_id,
            "count": len(pagination_data["results"]),
            "results": pagination_data["results"],
            "pagination": pagination_data["pagination"],
            "search_query": search_data.get("search_query", ""),
            "usage": usage,
        })

    except Exception:
        current_app.logger.exception("Search failed.")

        if search_id:
            try:
                delete_search(search_id)
            except Exception:
                current_app.logger.exception(
                    "Could not delete failed search cache."
                )

        return jsonify({
            "success": False,
            "message": (
                "Search failed. Please check your settings "
                "and try again."
            ),
        }), 500


# =====================================================
# PAGINATION PAGE
# Uses cached results.
# Does not call Google API or consume a search credit.
# =====================================================

@search_bp.route("/api/search/page", methods=["POST"])
def search_page():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please login before viewing search results.",
        }), 401

    data = request.get_json(silent=True) or {}

    search_id = str(data.get("search_id", "")).strip()

    try:
        page = int(data.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    page = max(page, 1)

    if not search_id:
        return jsonify({
            "success": False,
            "message": "Search session has expired. Please search again.",
        }), 400

    search_data = get_search(search_id)

    if not search_data:
        return jsonify({
            "success": False,
            "message": "Search session has expired. Please search again.",
        }), 404

    # Prevent users from accessing another user's cached search.
    # The cache record must contain the owner ID for this check.
    owner_id = search_data.get("user_id")

    if owner_id is not None and str(owner_id) != str(user.id):
        return jsonify({
            "success": False,
            "message": "You do not have access to these search results.",
        }), 403

    results = search_data.get("results", [])

    pagination_data = get_page_results(
        results=results,
        page=page,
    )

    pagination = pagination_data["pagination"]
    page_results = pagination_data["results"]

    return jsonify({
        "success": True,
        "search_id": search_id,
        "count": len(page_results),
        "results": page_results,
        "pagination": pagination,
        "search_query": (
            f"{search_data.get('keyword', '')} "
            f"in {search_data.get('city', '')}, "
            f"{search_data.get('country', '')}"
        ),
    })
