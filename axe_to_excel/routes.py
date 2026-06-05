"""Generate Axe 2 Excel routes.

Operation page + conversion API. Also hosts the shared ``/api/feature/sheets``
worksheet-picker endpoint used by the operation pages.
"""
from __future__ import annotations

import logging

from flask import Blueprint, request

from app_helpers import (fail, feature_response, ok, render_operation,
                         save_uploads)
from axe_to_excel import services

log = logging.getLogger("sde.axe_to_excel")

axe_to_excel_bp = Blueprint("axe_to_excel", __name__)


@axe_to_excel_bp.route("/generate-axe2-excel")
def page():
    return render_operation("generate-axe2-excel")


@axe_to_excel_bp.route("/api/feature/axe2excel", methods=["POST"])
def axe2excel():
    f = request.files.get("file")
    sheet = (request.form.get("sheet") or "").strip() or None
    parent_id = (request.form.get("parent_id") or "").strip()
    out_name = (request.form.get("out_name") or "").strip()
    try:
        paths = save_uploads([f])
        outputs, stats, preview = services.convert(
            paths[0], sheet=sheet, parent_id=parent_id, out_name=out_name)
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("axe2excel failed")
        return fail(f"Conversion failed: {exc}")
    return feature_response(outputs, stats, preview)


@axe_to_excel_bp.route("/api/feature/sheets", methods=["POST"])
def feature_sheets():
    """Return worksheet names for an uploaded workbook (shared sheet picker)."""
    f = request.files.get("file")
    try:
        paths = save_uploads([f])
        sheets = services.sheets_for(paths[0])
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        return fail(f"Could not read sheets: {exc}")
    return ok(sheets=sheets, file=paths[0].name)
