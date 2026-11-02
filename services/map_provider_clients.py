import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from flask import current_app

from services.monitoring import record_error


MAX_ATTEMPTS = 2
REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRY_DELAY_SECONDS = 2


class ProviderRequestError(RuntimeError):
    def __init__(self, provider, status_code=None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"{provider} search request failed.")


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(max(float(retry_after), 0), MAX_RETRY_DELAY_SECONDS)
        except ValueError:
            try:
                retry_time = parsedate_to_datetime(retry_after)
                if retry_time.tzinfo is None:
                    retry_time = retry_time.replace(tzinfo=timezone.utc)
                seconds = (retry_time - datetime.now(timezone.utc)).total_seconds()
                return min(max(seconds, 0), MAX_RETRY_DELAY_SECONDS)
            except (TypeError, ValueError, OverflowError):
                pass
    return min(0.25 * (2 ** attempt), MAX_RETRY_DELAY_SECONDS)


def request_json(
    provider,
    url,
    *,
    headers=None,
    params=None,
    timeout=None,
    method="GET",
    json_body=None,
):
    timeout = timeout or REQUEST_TIMEOUT_SECONDS
    last_status = None
    method = str(method).upper()
    if method not in {"GET", "POST"}:
        raise ValueError("Only GET and POST provider requests are supported.")

    for attempt in range(MAX_ATTEMPTS):
        try:
            request = requests.get if method == "GET" else requests.post
            request_args = {
                "headers": headers,
                "params": params,
                "timeout": timeout,
            }
            if method == "POST":
                request_args["json"] = json_body
            response = request(url, **request_args)
        except (requests.Timeout, requests.ConnectionError) as error:
            if attempt + 1 == MAX_ATTEMPTS:
                raise ProviderRequestError(provider) from error
            time.sleep(min(0.25 * (2 ** attempt), MAX_RETRY_DELAY_SECONDS))
            continue
        except requests.RequestException as error:
            raise ProviderRequestError(provider) from error

        last_status = response.status_code
        if response.status_code == 429 or response.status_code in {
            500, 502, 503, 504,
        }:
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(_retry_delay(response, attempt))
                continue
            raise ProviderRequestError(provider, last_status)

        if not response.ok:
            raise ProviderRequestError(provider, last_status)

        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderRequestError(provider, last_status) from error

        if not isinstance(payload, dict):
            raise ProviderRequestError(provider, last_status)
        return payload

    raise ProviderRequestError(provider, last_status)


def _search_query(country, city, keyword):
    keyword = str(keyword or "").strip()
    return f"{keyword} in {city}, {country}"


def search_google_places(country, city, keyword, plan):
    from services.google_places import GooglePlacesError, GooglePlacesService
    from services.plan_limits import PLAN_LIMITS

    enabled = bool(current_app.config.get("GOOGLE_MAPS_ENABLED", True))
    api_key = str(current_app.config.get("GOOGLE_MAPS_API_KEY") or "").strip()
    status = {"count": 0}
    if not enabled:
        status["status"] = "Disabled"
        return {
            "results": [],
            "statuses": {"Google Maps": status},
            "search_query": _search_query(country, city, keyword),
            "successful_providers": 0,
        }
    if not api_key:
        status["status"] = "Not Configured"
        return {
            "results": [],
            "statuses": {"Google Maps": status},
            "search_query": _search_query(country, city, keyword),
            "successful_providers": 0,
        }

    try:
        search_data = GooglePlacesService(api_key).search_places(
            country=country,
            city=city,
            keyword=keyword,
            plan=plan,
        )
    except GooglePlacesError as error:
        status_code = error.status_code
        status.update({
            "status": "Failed",
            "message": (
                "Provider temporarily unavailable."
                if status_code in (429, 500, 502, 503, 504)
                else "Provider request could not be completed."
            ),
        })
        results = []
    except Exception as error:
        record_error(
            "google_places",
            "ERROR",
            "Google Maps search failed.",
            exception=error,
        )
        status.update({
            "status": "Failed",
            "message": "Provider request could not be completed.",
        })
        results = []
    else:
        results = search_data["results"]
        status.update({
            "status": "Success",
            "count": len(results),
        })

    maximum_results = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])[
        "results_per_search"
    ]
    successful = status["status"] == "Success"
    return {
        "results": (
            results[:maximum_results]
            if maximum_results is not None
            else results
        ),
        "statuses": {"Google Maps": status},
        "search_query": _search_query(country, city, keyword),
        "successful_providers": int(successful),
    }
