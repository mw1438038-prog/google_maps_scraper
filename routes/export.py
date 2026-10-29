
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
from models.exported_lead import ExportedLead
from routes.usage import get_current_user


# =========================================================
# BLUEPRINT
# =========================================================

export_bp = Blueprint("export", __name__)


# =========================================================
# HELPERS
# =========================================================

def _get_history(search_id, user_id):
    if not search_id:
        return None

    return SearchHistory.query.filter_by(
        search_id=str(search_id).strip(),
        user_id=user_id,
    ).first()


def _save_exported_leads(user, search_id, results):
    """
    Save leads only when an export is requested.
    Avoid saving duplicate leads for the same user.
    """

    if not user or not results:
        return

    history = _get_history(search_id, user.id)

    # Do not save leads belonging to an unknown search.
    if not history:
        return

    for lead in results:
        if not isinstance(lead, dict):
            continue

        name = str(lead.get("name") or "").strip()

        if not name:
            continue

        place_id = (
            lead.get("place_id")
            or lead.get("id")
            or None
        )

        address = str(
            lead.get("address") or ""
        ).strip() or None

        # Find an already-saved lead belonging to this user.
        existing = None

        if place_id:
            existing = ExportedLead.query.filter_by(
                user_id=user.id,
                place_id=str(place_id),
            ).first()

        if not existing:
            query = ExportedLead.query.filter(
                ExportedLead.user_id == user.id,
                ExportedLead.name == name,
            )

            if address:
                query = query.filter(
                    ExportedLead.address == address
                )
            else:
                query = query.filter(
                    ExportedLead.address.is_(None)
                )

            existing = query.first()

        if existing:
            # Keep existing record; don't create a duplicate.
            continue

        rating = _to_float(lead.get("rating"))
        reviews = _to_int(lead.get("reviews"))

        types = lead.get("types")

        db.session.add(
            ExportedLead(
                user_id=user.id,
                place_id=str(place_id) if place_id else None,
                name=name,
                address=address,
                phone=lead.get("phone") or None,
                website=lead.get("website") or None,
                email=lead.get("email") or None,
                facebook=lead.get("facebook") or None,
                instagram=lead.get("instagram") or None,
                linkedin=lead.get("linkedin") or None,
                twitter=lead.get("twitter") or None,
                other_social=lead.get("other_social") or None,
                rating=rating,
                reviews=reviews,
                maps_url=lead.get("maps_url") or None,
                types=types,
                country=history.country,
                city=history.city,
                keyword=history.keyword,
            )
        )

    db.session.flush()


def _record_export(search_id, results, user=None):
    user = user or get_current_user()

    if not user or not search_id:
        return

    history = _get_history(search_id, user.id)

    if not history:
        return

    # Save the exported leads before updating export counters.
    _save_exported_leads(user, search_id, results)

    history.export_count = (history.export_count or 0) + 1
    history.exported_leads = (
        (history.exported_leads or 0) + len(results)
    )
    history.last_exported_at = datetime.utcnow()

    db.session.commit()


def _to_float(value):
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _export_rows(results):
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

    fields = [
        "name",
        "phone",
        "website",
        "email",
        "facebook",
        "instagram",
        "linkedin",
        "twitter",
        "other_social",
        "address",
        "rating",
        "reviews",
        "maps_url",
        "types",
    ]

    return headers, fields


def _build_csv(results):
    headers, fields = _export_rows(results)

    output = StringIO(newline="")
    output.write("\ufeff")

    writer = csv.writer(
        output,
        lineterminator="\n",
    )

    writer.writerow(headers)

    for lead in results:
        if isinstance(lead, dict):
            writer.writerow([
                lead.get(field, "")
                for field in fields
            ])

    return output.getvalue()


def _build_excel(results):
    headers, fields = _export_rows(results)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Google Maps Leads"

    worksheet.append(headers)

    for lead in results:
        if isinstance(lead, dict):
            worksheet.append([
                lead.get(field, "")
                for field in fields
            ])

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

    for column, width in column_widths.items():
        worksheet.column_dimensions[column].width = width

    for cell in worksheet[1]:
        font = copy(cell.font)
        font.bold = True
        cell.font = font

    worksheet.freeze_panes = "A2"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return output


# =========================================================
# EXPORT CSV
# =========================================================

@export_bp.route("/api/export/csv", methods=["POST"])
def export_csv():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please log in to export leads.",
        }), 401

    data = request.get_json(silent=True) or {}
    results = data.get("results", [])
    search_id = data.get("search_id", "")

    if not isinstance(results, list) or not results:
        return jsonify({
            "success": False,
            "message": "No leads available to export.",
        }), 400

    history = _get_history(search_id, user.id)

    if not history:
        return jsonify({
            "success": False,
            "message": "Search history not found. Please search again.",
        }), 404

    csv_data = _build_csv(results)

    try:
        _record_export(search_id, results, user=user)
    except Exception:
        db.session.rollback()
        raise

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="google_maps_leads.csv"'
        },
    )


# =========================================================
# EXPORT EXCEL
# =========================================================

@export_bp.route("/api/export/excel", methods=["POST"])
def export_excel():
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please log in to export leads.",
        }), 401

    data = request.get_json(silent=True) or {}
    results = data.get("results", [])
    search_id = data.get("search_id", "")

    if not isinstance(results, list) or not results:
        return jsonify({
            "success": False,
            "message": "No leads available to export.",
        }), 400

    history = _get_history(search_id, user.id)

    if not history:
        return jsonify({
            "success": False,
            "message": "Search history not found. Please search again.",
        }), 404

    output = _build_excel(results)

    try:
        _record_export(search_id, results, user=user)
    except Exception:
        db.session.rollback()
        raise

    return send_file(
        output,
        as_attachment=True,
        download_name="google_maps_leads.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


# =========================================================
# EXPORT FROM SEARCH HISTORY
# =========================================================

@export_bp.route(
    "/api/export/history/<string:search_id>/<string:file_type>",
    methods=["GET"],
)
def export_search_history(search_id, file_type):
    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "Please log in to export leads.",
        }), 401

    file_type = file_type.strip().lower()

    if file_type not in {"csv", "xlsx"}:
        return jsonify({
            "success": False,
            "message": "Unsupported export format.",
        }), 400

    history = _get_history(search_id, user.id)

    if not history:
        return jsonify({
            "success": False,
            "message": "Search history not found.",
        }), 404

    results = history.results or []

    if not results:
        return jsonify({
            "success": False,
            "message": "This search has no leads to export.",
        }), 400

    if file_type == "csv":
        csv_data = _build_csv(results)
        file_data = BytesIO(csv_data.encode("utf-8"))
        mimetype = "text/csv; charset=utf-8"
        extension = "csv"
    else:
        file_data = _build_excel(results)
        mimetype = (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
        extension = "xlsx"

    try:
        _record_export(search_id, results, user=user)
    except Exception:
        db.session.rollback()
        raise

    file_data.seek(0)

    return send_file(
        file_data,
        as_attachment=True,
        download_name=(
            f"google_maps_leads_{history.city}.{extension}"
        ),
        mimetype=mimetype,
    )
