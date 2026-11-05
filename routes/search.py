
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, request, jsonify, current_app

from services.map_provider_clients import search_google_places
from services.monitoring import (
    mark_component_healthy_in_session,
    record_error,
)
from services.website_scraper import WebsiteScraper

from routes.pagination import paginate_results

from models.search_history import SearchHistory

from routes.usage import (
    get_current_user,
    can_search,
    consume_search,
    get_usage,
)
from services.google_places import GooglePlacesError, GooglePlacesService


# =====================================================
# BLUEPRINT
# =====================================================

search_bp = Blueprint("search", __name__)
WEBSITE_SCRAPE_WORKERS = 10


def _scrape_result_website(scraper, result, logger):
    try:
        return scraper.scrape(result.get("website", ""))
    except Exception:
        logger.warning(
            "Website enrichment failed; returning the result without it.",
            extra={"category": "website_scraper"},
            exc_info=False,
        )
        return {
            "email": "",
            "facebook": "",
            "instagram": "",
            "linkedin": "",
            "twitter": "",
            "other_social": "",
        }


def enrich_results_with_website_data(results, logger):
    if not results:
        return

    scraper = WebsiteScraper(timeout=3)
    max_workers = min(WEBSITE_SCRAPE_WORKERS, len(results))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        scraped_results = executor.map(
            lambda result: _scrape_result_website(
                scraper,
                result,
                logger,
            ),
            results,
        )

        for result, scraped_data in zip(results, scraped_results):
            result.update(scraped_data)


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
            "Your 10 Free searches for this month have been used. "
            "They reset at the start of next month. "
            "Please upgrade to Pro or Business to continue."
        )

    if plan == "pro":
        return (
            "You have reached your monthly Pro search limit. "
            "Please wait for your next billing cycle or upgrade."
        )

    if plan == "business":
        return (
            "Your Business subscription is not active. "
            "Please check your subscription to continue searching."
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

    try:
        user_plan = (user.plan or "free").lower().strip()
        search_data = search_google_places(
            country=country,
            city=city,
            keyword=keyword,
            plan=user_plan,
        )
        results = search_data.get("results", [])

        if not search_data["successful_providers"]:
            return jsonify({
                "success": False,
                "message": (
                    "Google Maps search is unavailable. Check its "
                    "configuration and try again."
                ),
                "provider_statuses": search_data["statuses"],
            }), 503

        enrich_results_with_website_data(results, current_app.logger)

        search_id = uuid.uuid4().hex

        history_record = SearchHistory(
            search_id=search_id,
            user_id=user.id,
            country=country,
            city=city,
            keyword=keyword,
            result_count=len(results),
            results=[
                {
                    "source": result.get("source", ""),
                    "google_place_id": str(
                        (
                            result.get("provider_ids", {}).get("google_maps")
                            if isinstance(result.get("provider_ids"), dict)
                            else None
                        )
                        or result.get("google_place_id")
                        or result.get("place_id")
                        or result.get("provider_id")
                        or result.get("id")
                        or ""
                    ),
                }
                for result in results
            ],
        )

        if search_data["statuses"]["Google Maps"]["status"] == "Success":
            mark_component_healthy_in_session(
                "google_places",
                "observed_places_search",
            )

        # A combined provider search is one user search and one quota debit.
        if not consume_search(user, history_record):
            return jsonify({
                "success": False,
                "message": get_limit_message(user),
                "usage": get_usage(user),
                "provider_statuses": search_data["statuses"],
            }), 403

        pagination = paginate_results(
            results,
            page=1,
            per_page=15,
        )

        usage = get_usage(user)

        return jsonify({
            "success": True,
            "search_id": search_id,
            "count": len(results),
            "results": results,
            "pagination": pagination["pagination"],
            "search_query": search_data.get("search_query", ""),
            "provider_statuses": search_data["statuses"],
            "usage": usage,
        })

    except Exception as error:
        record_error(
            "search",
            "ERROR",
            "Combined maps search failed.",
            exception=error,
            status=500,
        )
        current_app.logger.exception("Search failed.")

        return jsonify({
            "success": False,
            "message": (
                "Search could not be completed. Please try again."
            ),
        }), 500


@search_bp.route("/api/google/place-details", methods=["POST"])
def google_place_details():
    user = get_current_user()
    if not user:
        return jsonify({
            "success": False,
            "message": "Please log in to view place details.",
        }), 401

    data = request.get_json(silent=True) or {}
    place_id = str(data.get("place_id") or "").strip()
    if (
        not place_id
        or len(place_id) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in place_id)
    ):
        return jsonify({
            "success": False,
            "message": "A valid Google Place ID is required.",
        }), 400

    user_history = SearchHistory.query.filter_by(user_id=user.id).all()
    if not any(
        isinstance(saved_result, dict)
        and saved_result.get("google_place_id") == place_id
        for history in user_history
        for saved_result in (history.results or [])
    ):
        return jsonify({
            "success": False,
            "message": "Place details are available only for your saved searches.",
        }), 404

    api_key = current_app.config.get("GOOGLE_MAPS_API_KEY")
    if not api_key or not current_app.config.get("GOOGLE_MAPS_ENABLED", True):
        return jsonify({
            "success": False,
            "message": "Google Maps details are not configured.",
        }), 503

    try:
        place = GooglePlacesService(api_key).get_place_details(place_id)
    except GooglePlacesError:
        return jsonify({
            "success": False,
            "message": "Google Maps could not retrieve these details right now.",
        }), 502

    display_name = place.get("displayName")
    return jsonify({
        "success": True,
        "source": "Google Maps",
        "name": (
            display_name.get("text", "")
            if isinstance(display_name, dict)
            else ""
        ),
        "address": place.get("formattedAddress", ""),
        "phone": place.get("nationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "rating": place.get("rating", ""),
        "reviews": place.get("userRatingCount", ""),
        "maps_url": place.get("googleMapsUri", ""),
        "attribution": "Google Maps",
    })


# =====================================================
# RETIRED PAGINATION ENDPOINT
# Results are paginated in the browser from the current search response.
# =====================================================

@search_bp.route("/api/search/page", methods=["POST"])
def search_page():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please login before viewing search results.",
        }), 401

    return jsonify({
        "success": False,
        "message": (
            "Search result pages are held only in the current browser session. "
            "Run a new search after reloading the page."
        ),
    }), 410
