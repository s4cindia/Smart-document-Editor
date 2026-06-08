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
from services import feature_service

log = logging.getLogger("sde.axe_to_excel")

axe_to_excel_bp = Blueprint("axe_to_excel", __name__)


# --------------------------------------------------------------------------
# Shared template management (used by placeholder 2 + placeholder 3)
# Lets users supply / replace / remove the optional WCAG audit template from
# the UI instead of hand-placing a file in data/templates/.
# --------------------------------------------------------------------------
@axe_to_excel_bp.route("/api/template/status")
def template_status():
    st = feature_service.template_status()
    return ok(found=st["found"], name=feature_service.WCAG_TEMPLATE.name)


@axe_to_excel_bp.route("/api/template/upload", methods=["POST"])
def template_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return fail("No template file selected.")
    if not f.filename.lower().endswith((".xlsx", ".xlsm")):
        return fail("The template must be an Excel .xlsx (or .xlsm) file.")
    try:
        feature_service.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        f.save(str(feature_service.WCAG_TEMPLATE))
        from openpyxl import load_workbook
        load_workbook(feature_service.WCAG_TEMPLATE).close()  # validate it opens
    except Exception as exc:  # noqa: BLE001
        try:
            feature_service.WCAG_TEMPLATE.unlink()
        except OSError:
            pass
        log.exception("template upload failed")
        return fail(f"Could not use that template: {exc}")
    return ok(found=True, name=feature_service.WCAG_TEMPLATE.name,
              uploaded=f.filename)


@axe_to_excel_bp.route("/api/template/clear", methods=["POST"])
def template_clear():
    try:
        if feature_service.WCAG_TEMPLATE.exists():
            feature_service.WCAG_TEMPLATE.unlink()
    except OSError as exc:
        return fail(f"Could not remove template: {exc}")
    return ok(found=False, name=feature_service.WCAG_TEMPLATE.name)


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
