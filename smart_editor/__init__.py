"""Smart Editor module.

Owns the editor's data backend: file open/sheets, the AG Grid data model
(columns/rows/edits/undo-redo), validation + duplicate checks, transforms,
analytics, export/report, and the PDF tools. Business logic lives in the
shared ``services`` package; ``services.py``, ``excel_processor.py`` and
``validators.py`` here are thin facades onto it.
"""
from smart_editor.routes import (  # noqa: F401
    analytics_bp,
    check_bp,
    data_bp,
    export_bp,
    files_bp,
    pdf_bp,
    transform_bp,
)
