"""Generate Excel for Downloadable routes — operation page + API."""
from __future__ import annotations

import logging

from flask import Blueprint, request

from app_helpers import (fail, feature_response, render_operation,
                         save_uploads)
from downloadable_audit import services

log = logging.getLogger("sde.downloadable")

downloadable_bp = Blueprint("downloadable_audit", __name__)


@downloadable_bp.route("/generate-downloadable-excel")
def page():
    return render_operation("generate-downloadable-excel")


@downloadable_bp.route("/api/feature/downloadable", methods=["POST"])
def downloadable():
    f = request.files.get("file")
    parent_id = (request.form.get("parent_id") or "").strip()
    sheet = (request.form.get("sheet") or "").strip() or None
    try:
        paths = save_uploads([f])
        outputs, stats, preview = services.generate(
            paths[0], parent_id=parent_id, sheet=sheet)
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("downloadable failed")
        return fail(f"Processing failed: {exc}")
    return feature_response(outputs, stats, preview)
