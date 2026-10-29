
import re
import requests
import geonamescache


PLACES_SEARCH_URL = (
    "https://places.googleapis.com/v1/places:searchText"
)

GOOGLE_PAGE_SIZE = 20


class GooglePlacesService:

    def __init__(self, api_key):
        self.api_key = api_key
        self.gc = geonamescache.GeonamesCache()
        self._city_names = None
        self._country_names = None

    # =====================================================
    # NORMALIZE TEXT
    # =====================================================

    def _normalize(self, value):
        if not value:
            return ""

        value = str(value).strip().lower()
        value = re.sub(r"[,\.\-_/]+", " ", value)
        value = re.sub(r"\s+", " ", value)

        return value.strip()

    # =====================================================
    # CITY NAMES
    # =====================================================

    def _get_city_names(self):
        if self._city_names is not None:
            return self._city_names

        city_names = set()

        for city in self.gc.get_cities().values():
            name = city.get("name", "")

            if name:
                normalized = self._normalize(name)

                if normalized:
                    city_names.add(normalized)

        self._city_names = city_names
        return self._city_names

    # =====================================================
    # COUNTRY NAMES
    # =====================================================

    def _get_country_names(self):
        if self._country_names is not None:
            return self._country_names

        country_names = set()

        for country in self.gc.get_countries().values():
            name = country.get("name", "")

            if name:
                normalized = self._normalize(name)

                if normalized:
                    country_names.add(normalized)

        self._country_names = country_names
        return self._country_names

    # =====================================================
    # REMOVE LOCATION WORDS FROM KEYWORD
    # =====================================================

    def _remove_location_names(self, keyword, city, country):
        if not keyword:
            return ""

        normalized_keyword = self._normalize(keyword)

        location_names = set()
        location_names.update(self._get_city_names())
        location_names.update(self._get_country_names())

        selected_city = self._normalize(city)
        selected_country = self._normalize(country)

        if selected_city:
            location_names.add(selected_city)

        if selected_country:
            location_names.add(selected_country)

        sorted_locations = sorted(
            location_names,
            key=len,
            reverse=True,
        )

        cleaned = normalized_keyword

        for location_name in sorted_locations:
            if not location_name:
                continue

            pattern = (
                rf"(?<!\w)"
                rf"{re.escape(location_name)}"
                rf"(?!\w)"
            )

            cleaned = re.sub(
                pattern,
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )

        return re.sub(r"\s+", " ", cleaned).strip()

    def _clean_keyword(self, keyword, city, country):
        keyword = str(keyword or "").strip()

        if not keyword:
            return ""

        return self._remove_location_names(
            keyword,
            city,
            country,
        )

    # =====================================================
    # BUILD SEARCH QUERY
    # =====================================================

    def _build_search_query(self, country, city, keyword):
        clean_keyword = self._clean_keyword(
            keyword,
            city,
            country,
        )

        if clean_keyword:
            return f"{clean_keyword} in {city}, {country}"

        return f"businesses in {city}, {country}"

    # =====================================================
    # LOCATION MATCH
    # =====================================================

    def _location_matches(self, result, country, city):
        requested_country = self._normalize(country)
        requested_city = self._normalize(city)

        actual_country = self._normalize(
            result.get("country", "")
        )
        actual_city = self._normalize(
            result.get("city", "")
        )

        if requested_country and actual_country != requested_country:
            return False

        if requested_city and actual_city != requested_city:
            return False

        return True

    # =====================================================
    # GOOGLE API REQUEST
    # =====================================================

    def _google_search_request(self, search_query, page_token=None):
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,"
                "places.displayName,"
                "places.formattedAddress,"
                "places.addressComponents,"
                "places.nationalPhoneNumber,"
                "places.internationalPhoneNumber,"
                "places.websiteUri,"
                "places.rating,"
                "places.userRatingCount,"
                "places.googleMapsUri,"
                "places.types,"
                "nextPageToken"
            ),
        }

        payload = {
            "textQuery": search_query,
            "pageSize": GOOGLE_PAGE_SIZE,
        }

        if page_token:
            payload["pageToken"] = page_token

        response = requests.post(
            PLACES_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if not response.ok:
            try:
                error_data = response.json()
            except ValueError:
                error_data = response.text

            raise Exception(
                f"Google Places API Error: {error_data}"
            )

        return response.json()

    # =====================================================
    # SEARCH PLACES
    #
    # No plan-based result limit.
    # Fetch available Google pages and remove duplicates.
    # =====================================================

    def search_places(
        self,
        country,
        city,
        keyword,
        plan="free",
    ):
        search_query = self._build_search_query(
            country,
            city,
            keyword,
        )

        print(f"[Google Places] Query: {search_query}")
        print(f"[Google Places] Plan: {plan}")
        print("[Google Places] Result limit: None")

        all_results = []
        seen_ids = set()
        page_token = None
        google_page = 1
        seen_tokens = set()

        while True:
            print(
                f"[Google Places] Fetching Google page "
                f"{google_page}"
            )

            data = self._google_search_request(
                search_query=search_query,
                page_token=page_token,
            )

            formatted_results = self._format_results(data)

            print(
                f"[Google Places] Google page "
                f"{google_page}: {len(formatted_results)} results"
            )

            for result in formatted_results:
                place_id = result.get("id", "")

                if place_id:
                    if place_id in seen_ids:
                        continue

                    seen_ids.add(place_id)

                all_results.append(result)

            next_page_token = data.get("nextPageToken")

            if not next_page_token:
                print("[Google Places] No more Google pages.")
                break

            if next_page_token in seen_tokens:
                print("[Google Places] Repeated page token; stopping.")
                break

            seen_tokens.add(next_page_token)
            page_token = next_page_token
            google_page += 1

        # =================================================
        # STRICT LOCATION FILTER
        # =================================================

        filtered_results = [
            result
            for result in all_results
            if self._location_matches(result, country, city)
        ]

        print(
            f"[Google Places] Unique results: "
            f"{len(all_results)}"
        )
        print(
            f"[Google Places] After location filter: "
            f"{len(filtered_results)}"
        )

        return {
            "results": filtered_results,
            "count": len(filtered_results),
            "search_query": search_query,
        }

    # =====================================================
    # FORMAT GOOGLE RESULTS
    # =====================================================

    def _format_results(self, data):
        results = []

        for place in data.get("places", []):
            location_data = self._get_location_components(place)

            display_name = place.get("displayName", {})
            name = display_name.get("text", "")

            results.append({
                "id": place.get("id", ""),
                "name": name,
                "address": place.get("formattedAddress", ""),
                "phone": (
                    place.get("internationalPhoneNumber")
                    or place.get("nationalPhoneNumber", "")
                ),
                "website": place.get("websiteUri", ""),
                "rating": place.get("rating", ""),
                "reviews": place.get("userRatingCount", ""),
                "maps_url": place.get("googleMapsUri", ""),
                "types": ", ".join(place.get("types", [])),
                "city": location_data.get("city", ""),
                "country": location_data.get("country", ""),
            })

        return results

    # =====================================================
    # GET ADDRESS COMPONENTS
    # =====================================================

    def _get_location_components(self, place):
        city = ""
        country = ""

        for component in place.get("addressComponents", []):
            types = component.get("types", [])

            name = (
                component.get("longText")
                or component.get("shortText")
                or ""
            )

            if "locality" in types and not city:
                city = name
            elif "postal_town" in types and not city:
                city = name

            if "country" in types:
                country = name

        return {
            "city": city,
            "country": country,
        }
