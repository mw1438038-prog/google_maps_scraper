
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
    if not user or not results:
        return

    history = _get_history(search_id, user.id)
    if not history:
        return

    for lead in results:
        if (
            not isinstance(lead, dict)
            or "Google Maps" not in lead.get("source", "")
        ):
            continue

        place_id = str(lead.get("place_id") or "").strip()
        if not place_id or len(place_id) > 255:
            continue

        existing = ExportedLead.query.filter_by(
            user_id=user.id,
            place_id=place_id,
        ).first()
        if existing:
            continue

        db.session.add(
            ExportedLead(
                user_id=user.id,
                place_id=place_id,
                name="Google Maps place",
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


def _history_export_rows(history):
    allowed_sources = {"Google Maps"}
    query = " in ".join(
        part
        for part in (
            str(history.keyword or "").strip(),
            ", ".join(
                part
                for part in (
                    str(history.city or "").strip(),
                    str(history.country or "").strip(),
                )
                if part
            ),
        )
        if part
    )
    export_rows = []

    for result in history.results or []:
        if not isinstance(result, dict):
            continue

        raw_sources = result.get("source") or result.get("sources")
        if isinstance(raw_sources, list):
            source_candidates = raw_sources
        elif isinstance(raw_sources, str):
            source_candidates = raw_sources.split(",")
        else:
            source_candidates = ["Google Maps"]

        sources = []
        for candidate in source_candidates:
            source = str(candidate).strip()
            if source in allowed_sources and source not in sources:
                sources.append(source)
        if not sources:
            continue

        place_id = ""
        if "Google Maps" in sources:
            place_id = str(
                result.get("google_place_id")
                or result.get("place_id")
                or result.get("id")
                or ""
            ).strip()
            if len(place_id) > 255 or any(
                ord(character) < 32 or ord(character) == 127
                for character in place_id
            ):
                place_id = ""

        export_rows.append({
            "source": ", ".join(sources),
            "place_id": place_id,
            "query": query,
        })

    return export_rows


def _search_export_rows(history, submitted_results):
    history_rows = _history_export_rows(history)
    if len(history_rows) != len(submitted_results):
        raise ValueError("Search results are incomplete. Please search again.")

    results_by_place_id = {}

    for result in submitted_results:
        if not isinstance(result, dict):
            raise ValueError("Search results are invalid. Please search again.")

        provider_ids = result.get("provider_ids")
        place_id = str(
            result.get("google_place_id")
            or (
                provider_ids.get("google_maps")
                if isinstance(provider_ids, dict)
                else ""
            )
            or result.get("place_id")
            or result.get("provider_id")
            or result.get("id")
            or ""
        ).strip()
        if not place_id or len(place_id) > 255 or place_id in results_by_place_id:
            raise ValueError("Search results are incomplete. Please search again.")

        results_by_place_id[place_id] = result

    export_rows = []
    matched_place_ids = set()
    for index, history_row in enumerate(history_rows):
        history_place_id = history_row["place_id"]
        if history_place_id:
            result = results_by_place_id.get(history_place_id)
            if result is None:
                raise ValueError("Search results are incomplete. Please search again.")
            place_id = history_place_id
        else:
            result = submitted_results[index]
            provider_ids = result.get("provider_ids")
            place_id = str(
                result.get("google_place_id")
                or (
                    provider_ids.get("google_maps")
                    if isinstance(provider_ids, dict)
                    else ""
                )
                or result.get("place_id")
                or result.get("id")
                or result.get("provider_id")
                or ""
            ).strip()

        if place_id in matched_place_ids:
            raise ValueError("Search results are incomplete. Please search again.")
        matched_place_ids.add(place_id)

        row = dict(history_row)
        row["place_id"] = place_id
        row.update({
            "name": result.get("name", ""),
            "phone": result.get("phone", ""),
            "website": result.get("website", ""),
            "email": result.get("email", ""),
            "facebook": result.get("facebook", ""),
            "instagram": result.get("instagram", ""),
            "linkedin": result.get("linkedin", ""),
            "twitter": result.get("twitter", ""),
            "other_social": result.get("other_social", ""),
            "address": result.get("address", ""),
            "rating": result.get("rating", ""),
            "reviews": result.get("reviews", ""),
            "maps_url": result.get("maps_url", ""),
        })
        export_rows.append(row)

    if len(matched_place_ids) != len(results_by_place_id):
        raise ValueError("Search results do not match this search.")

    return export_rows


def _safe_spreadsheet_cell(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _export_rows(include_details=False):
    if include_details:
        return (
            [
                "Source",
                "Google Place ID",
                "Business",
                "Phone",
                "Website",
                "Email",
                "Facebook",
                "Instagram",
                "LinkedIn",
                "Twitter / X",
                "Other Social",
                "Location",
                "Rating",
                "Reviews",
                "Google Maps",
                "Search Query",
            ],
            [
                "source",
                "place_id",
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
                "query",
            ],
        )

    return (
        ["Source", "Google Place ID", "Search Query"],
        ["source", "place_id", "query"],
    )


def _build_csv(results, include_details=False):
    headers, fields = _export_rows(include_details)

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
                _safe_spreadsheet_cell(lead.get(field, ""))
                for field in fields
            ])

    return output.getvalue()


def _build_excel(results, include_details=False):
    headers, fields = _export_rows(include_details)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Somo LeadFinder"

    worksheet.append(headers)

    for lead in results:
        if isinstance(lead, dict):
            worksheet.append([
                _safe_spreadsheet_cell(lead.get(field, ""))
                for field in fields
            ])

    widths = (
        24, 36, 32, 20, 36, 32, 32, 32,
        32, 32, 32, 48, 12, 12, 48, 80,
    )
    for column_index, width in enumerate(widths, start=1):
        if column_index <= worksheet.max_column:
            column = worksheet.cell(row=1, column=column_index).column_letter
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

    try:
        export_rows = _search_export_rows(history, results)
    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error),
        }), 400

    if not export_rows:
        return jsonify({
            "success": False,
            "message": "No permitted provider identifiers are available to export.",
        }), 400

    csv_data = _build_csv(export_rows, include_details=True)

    try:
        _record_export(search_id, export_rows, user=user)
    except Exception:
        db.session.rollback()
        raise

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="somo_leadfinder_leads.csv"'
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

    try:
        export_rows = _search_export_rows(history, results)
    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error),
        }), 400

    if not export_rows:
        return jsonify({
            "success": False,
            "message": "No permitted provider identifiers are available to export.",
        }), 400

    output = _build_excel(export_rows, include_details=True)

    try:
        _record_export(search_id, export_rows, user=user)
    except Exception:
        db.session.rollback()
        raise

    return send_file(
        output,
        as_attachment=True,
        download_name="somo_leadfinder_leads.xlsx",
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

    results = _history_export_rows(history)

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
            f"somo_leadfinder_leads_{history.city}.{extension}"
        ),
        mimetype=mimetype,
    )
