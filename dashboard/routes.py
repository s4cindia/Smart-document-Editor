"""Dashboard routes: landing page, editor shell, status + file downloads."""
from __future__ import annotations

import logging

from flask import Blueprint, render_template, request, send_file

from app_helpers import fail, ok, status_payload
from config import config
from utils import file_utils

log = logging.getLogger("sde.dashboard")

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@main_bp.route("/editor")
def index():
    return render_template("index.html")


@main_bp.route("/api/status")
def status():
    return ok(status=status_payload())


@main_bp.route("/download/<area>/<path:filename>")
def download(area: str, filename: str):
    folders = {"exports": config.export_dir, "reports": config.report_dir,
               "uploads": config.upload_dir}
    folder = folders.get(area)
    if folder is None:
        return fail("Unknown download area.", 404)
    target = (folder / filename).resolve()
    if not str(target).startswith(str(folder.resolve())) or not target.exists():
        return fail("File not found.", 404)
    # Honour a user-chosen name (?name=) so the saved file matches what the
    # rename dialog offered; keep the real file's extension if the user dropped
    # it, and fall back to the stored name when not provided.
    download_name = (request.args.get("name") or "").strip()
    if download_name:
        download_name = file_utils.safe_filename(download_name)
        if "." not in download_name and target.suffix:
            download_name += target.suffix
    return send_file(target, as_attachment=True,
                     download_name=download_name or None)
