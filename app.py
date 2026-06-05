"""Smart Document Editor & Validator — Flask application entry point.

Modular, blueprint-based architecture. Each feature lives in its own package
(auth, dashboard, smart_editor, merge_axe, axe_to_excel, downloadable_audit,
vpat_report); business logic is shared via the ``services`` package and the
SQLite user store lives in ``database``.

Run with:  python app.py   ->   http://127.0.0.1:5000

Authentication is login-only. Accounts are provisioned by an administrator
via create_user.py — there is no self-registration anywhere in the app.
"""
from __future__ import annotations

import logging
import traceback

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("smart_doc_editor")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MAX_CONTENT_LENGTH"] = config.max_content_length
    # Always pick up template/static edits without needing a full restart.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # Ensure the SQLite schema exists before serving any request.
    from database import init_db
    init_db()

    # ---- register feature blueprints --------------------------------------
    from auth import auth_bp
    from dashboard import main_bp
    from admin import admin_bp
    from smart_editor import (analytics_bp, check_bp, data_bp, export_bp,
                              files_bp, pdf_bp, transform_bp)
    from merge_axe import merge_axe_bp
    from axe_to_excel import axe_to_excel_bp
    from downloadable_audit import downloadable_bp
    from vpat_report import vpat_report_bp
    from vpat_editor import vpat_editor_bp

    for bp in (main_bp, auth_bp, admin_bp,
               files_bp, data_bp, check_bp, transform_bp, analytics_bp,
               export_bp, pdf_bp,
               merge_axe_bp, axe_to_excel_bp, downloadable_bp, vpat_report_bp,
               vpat_editor_bp):
        app.register_blueprint(bp)

    # ---- require login for everything except auth pages + static assets ----
    _PUBLIC_ENDPOINTS = {"auth.login", "auth.logout", "static"}

    @app.before_request
    def _require_login():
        if request.endpoint in _PUBLIC_ENDPOINTS:
            return None
        if session.get("user"):
            return None
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "Not authenticated"}), 401
        return redirect(url_for("auth.login"))

    @app.context_processor
    def _inject_user():
        return {"current_user": session.get("user"),
                "current_role": session.get("role")}

    @app.context_processor
    def _inject_asset_version():
        # bump to force browsers to reload updated css/js
        return {"asset_version": "40"}

    @app.errorhandler(403)
    def forbidden(_e):  # noqa: ANN001
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "Forbidden"}), 403
        return render_template("404.html"), 403

    @app.errorhandler(404)
    def not_found(_e):  # noqa: ANN001
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "Not found"}), 404
        return render_template("404.html"), 404

    @app.errorhandler(Exception)
    def handle_error(exc):  # noqa: ANN001
        log.error("Unhandled error: %s\n%s", exc, traceback.format_exc())
        return jsonify({"ok": False, "error": str(exc)}), 500

    log.info("Smart Document Editor ready (modular blueprints registered).")
    return app


app = create_app()


if __name__ == "__main__":
    print("=" * 60)
    print(" Smart Document Editor & Validator")
    print(" Open your browser at:  http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
