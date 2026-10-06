# =====================================================
# SEARCH CACHE
#
# Temporary in-memory cache for search results.
#
# Purpose:
# - Google API ko sirf new search par call karna
# - Next/Previous page par saved results use karna
# =====================================================

import uuid
import time


# =====================================================
# CACHE SETTINGS
# =====================================================

CACHE_TTL = 30 * 60
# 30 minutes


MAX_CACHE_ITEMS = 100


# =====================================================
# CACHE STORAGE
# =====================================================

_search_cache = {}


# =====================================================
# CREATE SEARCH ID
# =====================================================

def create_search_id():
    """
    Create a unique ID for a search.
    """

    return uuid.uuid4().hex


# =====================================================
# SAVE SEARCH
# =====================================================

def save_search(
    results,
    country,
    city,
    keyword
):
    """
    Save complete search results in memory.
    """

    search_id = create_search_id()

    _cleanup_cache()

    _search_cache[search_id] = {

        "created_at":
            time.time(),

        "country":
            country,

        "city":
            city,

        "keyword":
            keyword,

        "results":
            results,

    }

    return search_id


# =====================================================
# GET SEARCH
# =====================================================

def get_search(search_id):
    """
    Get saved search.
    """

    if not search_id:

        return None


    search_data = (
        _search_cache.get(
            search_id
        )
    )


    if not search_data:

        return None


    # =================================================
    # CHECK EXPIRATION
    # =================================================

    age = (
        time.time()
        -
        search_data["created_at"]
    )


    if age > CACHE_TTL:

        _search_cache.pop(
            search_id,
            None
        )

        return None


    return search_data


# =====================================================
# DELETE SEARCH
# =====================================================

def delete_search(search_id):
    """
    Delete one cached search.
    """

    if search_id:

        _search_cache.pop(
            search_id,
            None
        )


# =====================================================
# CLEAN OLD SEARCHES
# =====================================================

def _cleanup_cache():
    """
    Remove expired searches and keep
    cache size under control.
    """

    now = time.time()


    # =================================================
    # REMOVE EXPIRED
    # =================================================

    expired_ids = []


    for search_id, search_data in (
        _search_cache.items()
    ):

        age = (
            now
            -
            search_data["created_at"]
        )


        if age > CACHE_TTL:

            expired_ids.append(
                search_id
            )


    for search_id in expired_ids:

        _search_cache.pop(
            search_id,
            None
        )


    # =================================================
    # LIMIT CACHE SIZE
    # =================================================

    if (
        len(_search_cache)
        <= MAX_CACHE_ITEMS
    ):

        return


    # =================================================
    # OLDEST FIRST
    # =================================================

    sorted_items = sorted(

        _search_cache.items(),

        key=lambda item:
            item[1]["created_at"]

    )


    remove_count = (
        len(_search_cache)
        -
        MAX_CACHE_ITEMS
    )


    for search_id, _ in (
        sorted_items[:remove_count]
    ):

        _search_cache.pop(
            search_id,
            None
        )