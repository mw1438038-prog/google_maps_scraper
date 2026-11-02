
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
from routes.usage import get_current_user, get_plan_limits


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


def _history_export_rows(history, result_limit=None):
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

    return (
        export_rows[:result_limit]
        if result_limit is not None
        else export_rows
    )


def _safe_spreadsheet_cell(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _export_rows():
    return (
        ["Source", "Google Place ID", "Search Query"],
        ["source", "place_id", "query"],
    )


def _build_csv(results):
    headers, fields = _export_rows()

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


def _build_excel(results):
    headers, fields = _export_rows()

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

    column_widths = {
        "A": 30,
        "B": 36,
        "C": 80,
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

    export_rows = _history_export_rows(
        history,
        result_limit=get_plan_limits(user)["results_per_search"],
    )
    if not export_rows:
        return jsonify({
            "success": False,
            "message": "No permitted provider identifiers are available to export.",
        }), 400

    csv_data = _build_csv(export_rows)

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

    export_rows = _history_export_rows(
        history,
        result_limit=get_plan_limits(user)["results_per_search"],
    )
    if not export_rows:
        return jsonify({
            "success": False,
            "message": "No permitted provider identifiers are available to export.",
        }), 400

    output = _build_excel(export_rows)

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

    results = _history_export_rows(
        history,
        result_limit=get_plan_limits(user)["results_per_search"],
    )

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
