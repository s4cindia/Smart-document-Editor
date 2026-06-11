"""Help-lookup HTTP endpoints (self-contained blueprint).

Mounted at /api/help — independent of the editor's /api/data blueprint so the
Help feature can change without touching the rest of the app.

  POST /api/help/wcag-search  {q}  -> WCAG criteria  (ref / name / level)
  POST /api/help/axe-search   {q}  -> axe rules      (ruleId / tags / wcag ...)
"""
from __future__ import annotations

from flask import Blueprint, request

from app_helpers import ok
from help_lookup import service

help_bp = Blueprint("help", __name__, url_prefix="/api/help")


@help_bp.route("/wcag-search", methods=["POST"])
def wcag_search():
    body = request.get_json(force=True, silent=True) or {}
    return ok(**service.search_wcag(str(body.get("q") or "")))


@help_bp.route("/axe-search", methods=["POST"])
def axe_search():
    body = request.get_json(force=True, silent=True) or {}
    return ok(**service.search_axe(str(body.get("q") or "")))
