"""VPAT Editor module — web port of the uploaded vpat_editor.py.

Reuses the verbatim data model and reportlab PDF export from ``vpat_core`` and
exposes a browser-based editor (metadata, standards toggles, terms, and all
Level A/AA/AAA success criteria) with Export PDF / Save Draft / Open Draft.
"""
from vpat_editor.routes import vpat_editor_bp  # noqa: F401
