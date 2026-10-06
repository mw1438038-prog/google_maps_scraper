# =========================================================
# BACKEND PAGINATION
# =========================================================


# =========================================================
# SETTINGS
# =========================================================

PAGE_SIZE = 15


# =========================================================
# PAGINATE RESULTS
# =========================================================

def paginate_results(
    results,
    page=1,
    per_page=PAGE_SIZE
):

    # -----------------------------------------------------
    # SAFETY
    # -----------------------------------------------------

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1

    if page < 1:
        page = 1

    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = PAGE_SIZE

    if per_page < 1:
        per_page = PAGE_SIZE

    # -----------------------------------------------------
    # TOTAL
    # -----------------------------------------------------

    total = len(results)

    # -----------------------------------------------------
    # TOTAL PAGES
    # -----------------------------------------------------

    total_pages = (
        (total + per_page - 1)
        // per_page
    )

    # -----------------------------------------------------
    # EMPTY RESULTS
    # -----------------------------------------------------

    if total == 0:

        return {

            "results": [],

            "pagination": {

                "page": 1,

                "per_page": per_page,

                "total": 0,

                "total_pages": 0,

                "has_previous": False,

                "has_next": False,

                "previous_page": None,

                "next_page": None,

            }

        }

    # -----------------------------------------------------
    # PAGE OUT OF RANGE
    # -----------------------------------------------------

    if page > total_pages:

        page = total_pages

    # -----------------------------------------------------
    # START / END
    # -----------------------------------------------------

    start = (
        (page - 1)
        * per_page
    )

    end = start + per_page

    # -----------------------------------------------------
    # CURRENT PAGE RESULTS
    # -----------------------------------------------------

    page_results = results[
        start:end
    ]

    # -----------------------------------------------------
    # PAGINATION RESPONSE
    # -----------------------------------------------------

    return {

        "results": page_results,

        "pagination": {

            "page": page,

            "per_page": per_page,

            "total": total,

            "total_pages": total_pages,

            "has_previous": (
                page > 1
            ),

            "has_next": (
                page < total_pages
            ),

            "previous_page": (
                page - 1
                if page > 1
                else None
            ),

            "next_page": (
                page + 1
                if page < total_pages
                else None
            ),

        }

    }