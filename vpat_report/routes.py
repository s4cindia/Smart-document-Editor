"""VPAT / Delivery Outputs routes.

Delivery-outputs editor page plus the VPAT generation API and the two
delivery helpers (error summary + template export) used by that page.
"""
from __future__ import annotations

import logging

from flask import Blueprint, render_template, request

from app_helpers import fail, feature_response, ok, save_uploads
from services.store import store, drop_all_blank_rows
from utils.helpers import ID_COL
from vpat_report import services

log = logging.getLogger("sde.vpat_report")

vpat_report_bp = Blueprint("vpat_report", __name__)


@vpat_report_bp.route("/vpat-generate-report")
def page():
    # Opens the delivery-outputs editor (matches the reference toolbar).
    from services import feature_service
    return render_template("index.html", mode="delivery",
                           page_title="Validate / Generate Delivery Outputs",
                           template_found=feature_service.template_status()["found"])


@vpat_report_bp.route("/api/feature/vpat", methods=["POST"])
def vpat():
    f = request.files.get("file")
    try:
        paths = save_uploads([f])
        outputs, stats, preview = services.report(paths[0])
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("vpat failed")
        return fail(f"Report generation failed: {exc}")
    return feature_response(outputs, stats, preview)


@vpat_report_bp.route("/api/feature/delivery-errors", methods=["GET"])
def delivery_errors():
    if not store.loaded:
        return fail("Open a workbook first.")
    df = store.df.select([c for c in store.df.columns if c != ID_COL])
    return ok(summary=services.delivery_summary(df))


@vpat_report_bp.route("/api/feature/export-template", methods=["POST"])
def export_template():
    if not store.loaded:
        return fail("Open a workbook first.")
    # Downloads contain real data only: drop entirely-blank rows (every cell
    # null/empty) before stripping the internal id and writing the template.
    clean = drop_all_blank_rows(store.df, ID_COL)
    df = clean.select([c for c in clean.columns if c != ID_COL])
    try:
        out, used = services.export_template(df, stem="delivery")
    except Exception as exc:  # noqa: BLE001
        log.exception("export-template failed")
        return fail(f"Template export failed: {exc}")
    return ok(file=out.name, url=f"/download/exports/{out.name}",
              template_used=used)
