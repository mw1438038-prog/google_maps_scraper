
from io import BytesIO, StringIO
from copy import copy
import csv
from datetime import datetime

from flask import (
    Blueprint,
    request,
    jsonify,
    Response,
    send_file,
)

from openpyxl import Workbook

from extensions import db
from models.search_history import SearchHistory
from routes.usage import get_current_user


# =========================================================
# BLUEPRINT
# =========================================================

export_bp = Blueprint(
    "export",
    __name__,
)


def _record_export(search_id, results):
    user = get_current_user()

    if not user or not search_id:
        return

    history = SearchHistory.query.filter_by(
        search_id=str(search_id).strip(),
        user_id=user.id,
    ).first()

    if not history:
        return

    history.export_count = (history.export_count or 0) + 1
    history.exported_leads = (history.exported_leads or 0) + len(results)
    history.last_exported_at = datetime.utcnow()
    db.session.commit()


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

    search_id = data.get("search_id", "")

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

    _record_export(search_id, results)

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

    search_id = data.get("search_id", "")

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

    _record_export(search_id, results)

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


@export_bp.route(
    "/api/export/history/<string:search_id>/<string:file_type>",
    methods=["GET"],
)
def export_search_history(search_id, file_type):
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "message": "Please log in to export leads."}), 401

    file_type = file_type.strip().lower()
    if file_type not in {"csv", "xlsx"}:
        return jsonify({"success": False, "message": "Unsupported export format."}), 400

    history = SearchHistory.query.filter_by(
        search_id=search_id,
        user_id=user.id,
    ).first()
    if not history:
        return jsonify({"success": False, "message": "Search history not found."}), 404

    results = history.results or []
    if not results:
        return jsonify({"success": False, "message": "This search has no leads to export."}), 400

    headers = [
        "Business Name", "Phone", "Website", "Email", "Facebook",
        "Instagram", "LinkedIn", "Twitter", "Other Social", "Location",
        "Rating", "Reviews", "Google Maps", "Types",
    ]
    fields = [
        "name", "phone", "website", "email", "facebook", "instagram",
        "linkedin", "twitter", "other_social", "address", "rating",
        "reviews", "maps_url", "types",
    ]

    if file_type == "csv":
        output = StringIO(newline="")
        output.write("\ufeff")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(headers)
        for lead in results:
            writer.writerow([lead.get(field, "") for field in fields])
        file_data = BytesIO(output.getvalue().encode("utf-8"))
        output.close()
        mimetype = "text/csv; charset=utf-8"
        extension = "csv"
    else:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Google Maps Leads"
        worksheet.append(headers)
        for lead in results:
            worksheet.append([lead.get(field, "") for field in fields])
        worksheet.freeze_panes = "A2"
        file_data = BytesIO()
        workbook.save(file_data)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"

    history.export_count = (history.export_count or 0) + 1
    history.exported_leads = (history.exported_leads or 0) + len(results)
    history.last_exported_at = datetime.utcnow()
    db.session.commit()

    file_data.seek(0)
    return send_file(
        file_data,
        as_attachment=True,
        download_name=f"google_maps_leads_{history.city}.{extension}",
        mimetype=mimetype,
    )

