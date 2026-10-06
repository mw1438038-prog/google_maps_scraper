
from io import BytesIO, StringIO
from copy import copy
import csv

from flask import (
    Blueprint,
    request,
    jsonify,
    Response,
    send_file,
)

from openpyxl import Workbook


# =========================================================
# BLUEPRINT
# =========================================================

export_bp = Blueprint(
    "export",
    __name__,
)


# =========================================================
# EXPORT CSV
# =========================================================

@export_bp.route(
    "/api/export/csv",
    methods=["POST"]
)
def export_csv():

    data = request.get_json(
        silent=True
    ) or {}

    results = data.get(
        "results",
        []
    )

    if not results:

        return jsonify({

            "success": False,

            "message":
                "No leads available to export.",

        }), 400

    # =====================================================
    # CREATE CSV IN MEMORY
    # =====================================================

    output = StringIO(
        newline=""
    )

    # UTF-8 BOM for Excel
    output.write(
        "\ufeff"
    )

    writer = csv.writer(
        output,
        lineterminator="\n"
    )

    # =====================================================
    # HEADERS
    # =====================================================

    writer.writerow([

        "Business Name",

        "Phone",

        "Website",

        "Email",

        "Facebook",

        "Instagram",

        "LinkedIn",

        "Twitter",

        "Other Social",

        "Location",

        "Rating",

        "Reviews",

        "Google Maps",

        "Types",

    ])

    # =====================================================
    # DATA
    # =====================================================

    for place in results:

        writer.writerow([

            place.get(
                "name",
                ""
            ),

            place.get(
                "phone",
                ""
            ),

            place.get(
                "website",
                ""
            ),

            place.get(
                "email",
                ""
            ),

            place.get(
                "facebook",
                ""
            ),

            place.get(
                "instagram",
                ""
            ),

            place.get(
                "linkedin",
                ""
            ),

            place.get(
                "twitter",
                ""
            ),

            place.get(
                "other_social",
                ""
            ),

            place.get(
                "address",
                ""
            ),

            place.get(
                "rating",
                ""
            ),

            place.get(
                "reviews",
                ""
            ),

            place.get(
                "maps_url",
                ""
            ),

            place.get(
                "types",
                ""
            ),

        ])

    csv_data = output.getvalue()

    output.close()

    # =====================================================
    # SEND CSV
    # =====================================================

    return Response(

        csv_data,

        mimetype=(
            "text/csv; charset=utf-8"
        ),

        headers={

            "Content-Disposition":
                "attachment; "
                "filename="
                "google_maps_leads.csv"

        },

    )


# =========================================================
# EXPORT EXCEL
# =========================================================

@export_bp.route(
    "/api/export/excel",
    methods=["POST"]
)
def export_excel():

    data = request.get_json(
        silent=True
    ) or {}

    results = data.get(
        "results",
        []
    )

    if not results:

        return jsonify({

            "success": False,

            "message":
                "No leads available to export.",

        }), 400

    # =====================================================
    # CREATE WORKBOOK
    # =====================================================

    workbook = Workbook()

    worksheet = (
        workbook.active
    )

    worksheet.title = (
        "Google Maps Leads"
    )

    # =====================================================
    # HEADERS
    # =====================================================

    headers = [

        "Business Name",

        "Phone",

        "Website",

        "Email",

        "Facebook",

        "Instagram",

        "LinkedIn",

        "Twitter",

        "Other Social",

        "Location",

        "Rating",

        "Reviews",

        "Google Maps",

        "Types",

    ]

    worksheet.append(
        headers
    )

    # =====================================================
    # DATA
    # =====================================================

    for place in results:

        worksheet.append([

            place.get(
                "name",
                ""
            ),

            place.get(
                "phone",
                ""
            ),

            place.get(
                "website",
                ""
            ),

            place.get(
                "email",
                ""
            ),

            place.get(
                "facebook",
                ""
            ),

            place.get(
                "instagram",
                ""
            ),

            place.get(
                "linkedin",
                ""
            ),

            place.get(
                "twitter",
                ""
            ),

            place.get(
                "other_social",
                ""
            ),

            place.get(
                "address",
                ""
            ),

            place.get(
                "rating",
                ""
            ),

            place.get(
                "reviews",
                ""
            ),

            place.get(
                "maps_url",
                ""
            ),

            place.get(
                "types",
                ""
            ),

        ])

    # =====================================================
    # COLUMN WIDTHS
    # =====================================================

    column_widths = {

        "A": 40,

        "B": 20,

        "C": 45,

        "D": 35,

        "E": 45,

        "F": 45,

        "G": 45,

        "H": 45,

        "I": 60,

        "J": 70,

        "K": 12,

        "L": 12,

        "M": 60,

        "N": 40,

    }

    for column, width in (
        column_widths.items()
    ):

        worksheet.column_dimensions[
            column
        ].width = width

    # =====================================================
    # HEADER BOLD
    # =====================================================

    for cell in worksheet[1]:

        font = copy(
            cell.font
        )

        font.bold = True

        cell.font = font

    # =====================================================
    # FREEZE HEADER
    # =====================================================

    worksheet.freeze_panes = (
        "A2"
    )

    # =====================================================
    # SAVE TO MEMORY
    # =====================================================

    output = BytesIO()

    workbook.save(
        output
    )

    output.seek(0)

    # =====================================================
    # SEND EXCEL
    # =====================================================

    return send_file(

        output,

        as_attachment=True,

        download_name=(
            "google_maps_leads.xlsx"
        ),

        mimetype=(
            "application/"
            "vnd.openxmlformats-"
            "officedocument."
            "spreadsheetml.sheet"
        ),

    )

