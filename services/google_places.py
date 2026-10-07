import re
import requests
import geonamescache


PLACES_SEARCH_URL = (
    "https://places.googleapis.com/v1/places:searchText"
)


# =====================================================
# GOOGLE PAGINATION SETTINGS
# =====================================================

GOOGLE_PAGE_SIZE = 20


# =====================================================
# PLAN RESULT LIMITS
# =====================================================

PLAN_RESULT_LIMITS = {

    "free": 15,

    "pro": 100,

    "business": 200,
}


class GooglePlacesService:

    def __init__(self, api_key):

        self.api_key = api_key

        # =================================================
        # GEONAMES CACHE
        # =================================================

        self.gc = geonamescache.GeonamesCache()

        self._city_names = None
        self._country_names = None

    # =====================================================
    # NORMALIZE TEXT
    # =====================================================

    def _normalize(self, value):

        if not value:
            return ""

        value = str(
            value
        ).strip().lower()

        value = re.sub(
            r"[,\.\-_/]+",
            " ",
            value
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        return value.strip()

    # =====================================================
    # CITY NAMES
    # =====================================================

    def _get_city_names(self):

        if self._city_names is not None:
            return self._city_names

        cities = self.gc.get_cities()

        city_names = set()

        for city in cities.values():

            name = city.get(
                "name",
                ""
            )

            if name:

                normalized = (
                    self._normalize(
                        name
                    )
                )

                if normalized:

                    city_names.add(
                        normalized
                    )

        self._city_names = city_names

        return self._city_names

    # =====================================================
    # COUNTRY NAMES
    # =====================================================

    def _get_country_names(self):

        if self._country_names is not None:
            return self._country_names

        countries = self.gc.get_countries()

        country_names = set()

        for country in countries.values():

            name = country.get(
                "name",
                ""
            )

            if name:

                normalized = (
                    self._normalize(
                        name
                    )
                )

                if normalized:

                    country_names.add(
                        normalized
                    )

        self._country_names = country_names

        return self._country_names

    # =====================================================
    # REMOVE LOCATION WORDS FROM KEYWORD
    # =====================================================

    def _remove_location_names(
        self,
        keyword,
        city,
        country
    ):

        if not keyword:
            return ""

        normalized_keyword = (
            self._normalize(
                keyword
            )
        )

        location_names = set()

        # -------------------------------------------------
        # ALL CITIES
        # -------------------------------------------------

        location_names.update(
            self._get_city_names()
        )

        # -------------------------------------------------
        # ALL COUNTRIES
        # -------------------------------------------------

        location_names.update(
            self._get_country_names()
        )

        # -------------------------------------------------
        # SELECTED CITY
        # -------------------------------------------------

        selected_city = (
            self._normalize(
                city
            )
        )

        if selected_city:

            location_names.add(
                selected_city
            )

        # -------------------------------------------------
        # SELECTED COUNTRY
        # -------------------------------------------------

        selected_country = (
            self._normalize(
                country
            )
        )

        if selected_country:

            location_names.add(
                selected_country
            )

        # -------------------------------------------------
        # LONGEST FIRST
        # -------------------------------------------------

        sorted_locations = sorted(
            location_names,
            key=len,
            reverse=True
        )

        cleaned = normalized_keyword

        # -------------------------------------------------
        # REMOVE LOCATION NAMES
        # -------------------------------------------------

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
                flags=re.IGNORECASE
            )

        # -------------------------------------------------
        # CLEAN SPACES
        # -------------------------------------------------

        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned
        ).strip()

        return cleaned

    # =====================================================
    # CLEAN KEYWORD
    # =====================================================

    def _clean_keyword(
        self,
        keyword,
        city,
        country
    ):

        keyword = str(
            keyword or ""
        ).strip()

        if not keyword:
            return ""

        return self._remove_location_names(
            keyword=keyword,
            city=city,
            country=country
        )

    # =====================================================
    # BUILD SEARCH QUERY
    # =====================================================

    def _build_search_query(
        self,
        country,
        city,
        keyword
    ):

        clean_keyword = (
            self._clean_keyword(
                keyword,
                city,
                country
            )
        )

        # -------------------------------------------------
        # NORMAL KEYWORD
        # -------------------------------------------------

        if clean_keyword:

            return (
                f"{clean_keyword} "
                f"in {city}, {country}"
            )

        # -------------------------------------------------
        # ONLY LOCATION
        # -------------------------------------------------

        return (
            f"businesses "
            f"in {city}, {country}"
        )

    # =====================================================
    # LOCATION MATCH
    # =====================================================

    def _location_matches(
        self,
        result,
        country,
        city
    ):

        requested_country = (
            self._normalize(
                country
            )
        )

        requested_city = (
            self._normalize(
                city
            )
        )

        actual_country = (
            self._normalize(
                result.get(
                    "country",
                    ""
                )
            )
        )

        actual_city = (
            self._normalize(
                result.get(
                    "city",
                    ""
                )
            )
        )

        # -------------------------------------------------
        # COUNTRY MUST MATCH
        # -------------------------------------------------

        if (
            requested_country
            and actual_country
            != requested_country
        ):

            return False

        # -------------------------------------------------
        # CITY MUST MATCH
        # -------------------------------------------------

        if (
            requested_city
            and actual_city
            != requested_city
        ):

            return False

        return True

    # =====================================================
    # GOOGLE API REQUEST
    # =====================================================

    def _google_search_request(
        self,
        search_query,
        page_token=None
    ):

        headers = {

            "Content-Type":
                "application/json",

            "X-Goog-Api-Key":
                self.api_key,

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

            "textQuery":
                search_query,

            "pageSize":
                GOOGLE_PAGE_SIZE,
        }

        # -------------------------------------------------
        # NEXT PAGE TOKEN
        # -------------------------------------------------

        if page_token:

            payload[
                "pageToken"
            ] = page_token

        # -------------------------------------------------
        # REQUEST
        # -------------------------------------------------

        response = requests.post(

            PLACES_SEARCH_URL,

            headers=headers,

            json=payload,

            timeout=30,
        )

        # -------------------------------------------------
        # ERROR
        # -------------------------------------------------

        if not response.ok:

            try:

                error_data = (
                    response.json()
                )

            except ValueError:

                error_data = (
                    response.text
                )

            raise Exception(
                f"Google Places API Error: "
                f"{error_data}"
            )

        return response.json()

    # =====================================================
    # GET PLAN RESULT LIMIT
    # =====================================================

    def _get_plan_result_limit(
        self,
        plan
    ):

        plan = str(
            plan or "free"
        ).lower().strip()

        return PLAN_RESULT_LIMITS.get(
            plan,
            PLAN_RESULT_LIMITS["free"]
        )

    # =====================================================
    # SEARCH PLACES
    #
    # GOOGLE PAGINATION IS INTERNAL
    #
    # Free:
    #   Google fetches only enough pages for 15 results
    #
    # Pro:
    #   Google fetches up to 100 results
    #
    # Business:
    #   Google fetches up to 200 results
    #
    # APP PAGINATION IS SEPARATE
    #
    # App:
    #   15 results per page
    #
    # =====================================================

    def search_places(
        self,
        country,
        city,
        keyword,
        plan="free"
    ):

        # =================================================
        # PLAN LIMIT
        # =================================================

        result_limit = (
            self._get_plan_result_limit(
                plan
            )
        )

        # =================================================
        # BUILD QUERY
        # =================================================

        search_query = (
            self._build_search_query(
                country,
                city,
                keyword
            )
        )

        print(
            f"[Google Places] Query: "
            f"{search_query}"
        )

        print(
            f"[Google Places] Plan: "
            f"{plan}"
        )

        print(
            f"[Google Places] Result limit: "
            f"{result_limit}"
        )

        # =================================================
        # ALL GOOGLE RESULTS
        # =================================================

        all_results = []

        page_token = None

        google_page = 1

        # =================================================
        # GOOGLE PAGINATION
        # =================================================

        while (
            len(all_results)
            < result_limit
        ):

            print(
                f"[Google Places] "
                f"Fetching Google page "
                f"{google_page}"
            )

            # -------------------------------------------------
            # GOOGLE REQUEST
            # -------------------------------------------------

            data = (
                self._google_search_request(
                    search_query=search_query,
                    page_token=page_token
                )
            )

            # -------------------------------------------------
            # FORMAT RESULTS
            # -------------------------------------------------

            formatted_results = (
                self._format_results(
                    data
                )
            )

            print(
                f"[Google Places] "
                f"Google page {google_page}: "
                f"{len(formatted_results)} results"
            )

            # -------------------------------------------------
            # ADD RESULTS
            # -------------------------------------------------

            all_results.extend(
                formatted_results
            )

            # -------------------------------------------------
            # NEXT PAGE TOKEN
            # -------------------------------------------------

            next_page_token = (
                data.get(
                    "nextPageToken"
                )
            )

            # -------------------------------------------------
            # NO MORE PAGES
            # -------------------------------------------------

            if not next_page_token:

                print(
                    "[Google Places] "
                    "No more Google pages."
                )

                break

            # -------------------------------------------------
            # CHECK IF ENOUGH RESULTS
            # -------------------------------------------------

            if len(all_results) >= result_limit:

                print(
                    "[Google Places] "
                    "Plan result limit reached."
                )

                break

            # -------------------------------------------------
            # NEXT PAGE
            # -------------------------------------------------

            page_token = (
                next_page_token
            )

            google_page += 1

        # =====================================================
        # REMOVE DUPLICATES
        # =====================================================

        unique_results = []

        seen_ids = set()

        for result in all_results:

            place_id = result.get(
                "id",
                ""
            )

            if place_id:

                if place_id in seen_ids:
                    continue

                seen_ids.add(
                    place_id
                )

            unique_results.append(
                result
            )

        # =====================================================
        # STRICT LOCATION FILTER
        # =====================================================

        filtered_results = []

        for result in unique_results:

            if self._location_matches(
                result,
                country,
                city
            ):

                filtered_results.append(
                    result
                )

        # =====================================================
        # APPLY PLAN LIMIT AFTER FILTER
        # =====================================================

        filtered_results = (
            filtered_results[
                :result_limit
            ]
        )

        # =====================================================
        # DEBUG
        # =====================================================

        print(
            f"[Google Places] "
            f"Total Google results: "
            f"{len(unique_results)}"
        )

        print(
            f"[Google Places] "
            f"After city/country filter: "
            f"{len(filtered_results)}"
        )

        print(
            f"[Google Places] "
            f"Final plan results: "
            f"{len(filtered_results)}"
        )

        # =====================================================
        # RETURN
        # =====================================================

        return {

            "results":
                filtered_results,

            "count":
                len(
                    filtered_results
                ),

            "search_query":
                search_query,
        }

    # =====================================================
    # FORMAT GOOGLE RESULTS
    # =====================================================

    def _format_results(
        self,
        data
    ):

        results = []

        for place in data.get(
            "places",
            []
        ):

            # -------------------------------------------------
            # LOCATION
            # -------------------------------------------------

            location_data = (
                self._get_location_components(
                    place
                )
            )

            actual_city = (
                location_data.get(
                    "city",
                    ""
                )
            )

            actual_country = (
                location_data.get(
                    "country",
                    ""
                )
            )

            # -------------------------------------------------
            # NAME
            # -------------------------------------------------

            display_name = (
                place.get(
                    "displayName",
                    {}
                )
            )

            name = (
                display_name.get(
                    "text",
                    ""
                )
            )

            # -------------------------------------------------
            # RESULT
            # -------------------------------------------------

            results.append({

                "id":
                    place.get(
                        "id",
                        ""
                    ),

                "name":
                    name,

                "address":
                    place.get(
                        "formattedAddress",
                        ""
                    ),

                "phone": (
                    place.get(
                        "internationalPhoneNumber"
                    )
                    or
                    place.get(
                        "nationalPhoneNumber",
                        ""
                    )
                ),

                "website":
                    place.get(
                        "websiteUri",
                        ""
                    ),

                "rating":
                    place.get(
                        "rating",
                        ""
                    ),

                "reviews":
                    place.get(
                        "userRatingCount",
                        ""
                    ),

                "maps_url":
                    place.get(
                        "googleMapsUri",
                        ""
                    ),

                "types":
                    ", ".join(
                        place.get(
                            "types",
                            []
                        )
                    ),

                "city":
                    actual_city,

                "country":
                    actual_country,
            })

        return results

    # =====================================================
    # GET ADDRESS COMPONENTS
    # =====================================================

    def _get_location_components(
        self,
        place
    ):

        city = ""

        country = ""

        for component in place.get(
            "addressComponents",
            []
        ):

            types = component.get(
                "types",
                []
            )

            name = (
                component.get(
                    "longText"
                )
                or
                component.get(
                    "shortText"
                )
                or
                ""
            )

            # =============================================
            # CITY
            # =============================================

            if (
                "locality" in types
                and not city
            ):

                city = name

            elif (
                "postal_town" in types
                and not city
            ):

                city = name

            # =============================================
            # COUNTRY
            # =============================================

            if "country" in types:

                country = name

        return {

            "city":
                city,

            "country":
                country,
        }