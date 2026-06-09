"""Merge Axe Tool Excels routes.

Page (editor in "merge" mode) plus the merge API and the merge-then-open
endpoint that loads the merged workbook straight into the editor grid.
"""
from __future__ import annotations

import logging

from flask import Blueprint, render_template, request

from app_helpers import (fail, feature_response, load_tabular, ok,
                         save_uploads, status_payload)
from merge_axe import services

log = logging.getLogger("sde.merge_axe")

merge_axe_bp = Blueprint("merge_axe", __name__)


@merge_axe_bp.route("/merge-axe-excels")
def page():
    # Opens the full editor with an added "Merge Files" capability.
    return render_template("index.html", mode="merge",
                           page_title="Validate /Merge Axe Tool Excels")


@merge_axe_bp.route("/api/feature/merge-axe", methods=["POST"])
def merge_axe():
    files = request.files.getlist("files") or request.files.getlist("file")
    try:
        paths = save_uploads(files)
        outputs, stats, preview = services.merge(paths)
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("merge-axe failed")
        return fail(f"Merge failed: {exc}")
    return feature_response(outputs, stats, preview)


@merge_axe_bp.route("/api/files/merge-open", methods=["POST"])
def merge_open():
    """Merge multiple axe workbooks and load the result into the editor grid."""
    files = request.files.getlist("files") or request.files.getlist("file")
    try:
        paths = save_uploads(files)
        outputs, stats, _preview = services.merge(paths)
        merged_path = outputs[0][1]
        load_tabular(merged_path, sort_id=True)
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("merge-open failed")
        return fail(f"Merge failed: {exc}")
    return ok(loaded=True, status=status_payload(), stats=stats,
              merged_file=merged_path.name,
              merge_url=f"/download/exports/{merged_path.name}")
