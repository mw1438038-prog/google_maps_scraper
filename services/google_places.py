import requests


PLACES_SEARCH_URL = (
    "https://places.googleapis.com/v1/places:searchText"
)


class GooglePlacesService:

    def __init__(self, api_key):
        self.api_key = api_key

    def search_places(self, country, city, keyword):

        search_query = (
            f"{keyword} in {city}, {country}"
        )

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,"
                "places.displayName,"
                "places.formattedAddress,"
                "places.nationalPhoneNumber,"
                "places.internationalPhoneNumber,"
                "places.websiteUri,"
                "places.rating,"
                "places.userRatingCount,"
                "places.googleMapsUri,"
                "places.types"
            ),
        }

        payload = {
            "textQuery": search_query,
            "pageSize": 20,
        }

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

        data = response.json()

        return self._format_results(data)

    def _format_results(self, data):

        results = []

        for place in data.get("places", []):

            display_name = place.get(
                "displayName",
                {}
            )

            results.append({
                "id": place.get("id", ""),

                "name": display_name.get(
                    "text",
                    ""
                ),

                "address": place.get(
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

                "website": place.get(
                    "websiteUri",
                    ""
                ),

                "rating": place.get(
                    "rating",
                    ""
                ),

                "reviews": place.get(
                    "userRatingCount",
                    ""
                ),

                "maps_url": place.get(
                    "googleMapsUri",
                    ""
                ),

                "types": ", ".join(
                    place.get("types", [])
                ),
            })

        return results