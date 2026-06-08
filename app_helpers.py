"""Shared web-layer helpers used by the feature route modules.

These keep the per-feature ``routes.py`` files thin: JSON envelope helpers,
the upload-saving guard, the data-store status payload, and the loaders that
pull an uploaded file into the in-memory store. Business logic itself lives in
the ``services`` package (single source of truth); this module only adapts it
to the Flask request/response layer.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from flask import abort, jsonify, render_template

from config import config
from services import (csv_service, excel_service, feature_service, pdf_service)
from services.store import FileMeta, store, drop_all_blank_rows
from utils import file_utils
from utils.helpers import data_columns

log = logging.getLogger("sde.web")


# --------------------------------------------------------------------------
# JSON envelope helpers
# --------------------------------------------------------------------------
def ok(**payload: Any):
    payload.setdefault("ok", True)
    return jsonify(payload)


def fail(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


# --------------------------------------------------------------------------
# Data-store status
# --------------------------------------------------------------------------
def status_payload() -> dict[str, Any]:
    if not store.loaded:
        return {
            "loaded": False, "file": "No file loaded", "size": "-",
            "rows": 0, "cols": 0, "source": "-",
            "can_undo": store.can_undo(), "can_redo": store.can_redo(),
        }
    df = store.df
    return {
        "loaded": True,
        "file": store.meta.name,
        "size": store.meta.size or "-",
        "sheet": store.meta.sheet,
        "source": store.meta.source,
        "rows": df.height,
        "cols": len(data_columns(df)),
        "can_undo": store.can_undo(),
        "can_redo": store.can_redo(),
    }


# --------------------------------------------------------------------------
# Uploads + feature response
# --------------------------------------------------------------------------
def save_uploads(files) -> list[Path]:
    """Validate + persist uploaded files; return saved paths."""
    saved: list[Path] = []
    for f in files:
        if not f or not f.filename:
            continue
        if not file_utils.allowed_file(f.filename):
            raise ValueError(f"Unsupported file type: {f.filename}")
        dest = file_utils.unique_path(config.upload_dir,
                                      file_utils.safe_filename(f.filename))
        f.save(dest)
        saved.append(dest)
    if not saved:
        raise ValueError("No valid files were uploaded.")
    return saved


def feature_response(outputs, stats, preview):
    files = [{"label": label, "file": p.name,
              "url": f"/download/exports/{p.name}"} for label, p in outputs]
    return ok(files=files, stats=stats, preview=preview)


# --------------------------------------------------------------------------
# Loaders (tabular + pdf) — shared by the editor + merge-open
# --------------------------------------------------------------------------
def load_tabular(path: Path, sheet: str | None = None, max_cols: int = 18) -> None:
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = excel_service.read_sheet(path, sheet)
        source = "excel"
    elif ext in (".csv", ".tsv"):
        df = csv_service.read_csv(path)
        source = "csv"
    else:
        raise ValueError(f"Unsupported tabular type: {ext}")
    # Trim trailing columns beyond the expected range so stray content never
    # reaches the editor. Merge / main editor keep A-R (18); the delivery
    # editor keeps A-W (23). Controlled by max_cols from the caller.
    if df.width > max_cols:
        df = df.select(df.columns[:max_cols])
    # Remove rows where the WHOLE row is blank (every cell null/empty) so the
    # user only ever sees real data. Rows with some empty cells are kept.
    df = drop_all_blank_rows(df)
    meta = FileMeta(
        path=str(path), name=path.name, ext=ext,
        size=file_utils.human_size(path.stat().st_size),
        sheet=sheet, source=source,
    )
    store.set_dataframe(df, meta)
    file_utils.add_recent(path, sheet)


def load_pdf(path: Path) -> None:
    meta = pdf_service.extract_metadata(path)
    text = pdf_service.extract_text(path)
    tables = pdf_service.extract_tables(path)
    store._df = None  # PDFs are not tabular until a table is chosen
    store.meta = FileMeta(path=str(path), name=path.name, ext=".pdf",
                          size=file_utils.human_size(path.stat().st_size),
                          source="pdf")
    store.extra = {"meta": meta, "text": text, "tables": tables}
    file_utils.add_recent(path)


def pdf_info_payload() -> dict[str, Any]:
    tables = store.extra.get("tables", [])
    return {
        "meta": store.extra.get("meta", {}),
        "page_count": store.extra.get("meta", {}).get("pages", 0),
        "tables": [{"page": t["page"], "index": t["index"],
                    "columns": t["columns"], "rows": t["rows"]} for t in tables],
        "text_pages": len(store.extra.get("text", [])),
    }


# --------------------------------------------------------------------------
# Feature operation-page metadata (axe2excel / downloadable use operation.html)
# --------------------------------------------------------------------------
OPERATIONS = {
    "generate-axe2-excel": {
        "title": "Generate Axe 2 Excel",
        "description": "Convert axe DevTools output into the S4Carlisle audit Excel "
                       "format. Pick the sheet, set a Parent ID, preview and export.",
        "accent": "#0d9488",
        "endpoint": "/api/feature/axe2excel",
        "multiple": False, "accept": ".xlsx,.xls,.csv",
        "cta": "Generate Audit Workbook",
        "input_label": "Upload an axe DevTools export workbook",
        "need_sheet": True, "need_parent_id": True, "need_out_name": True,
    },
    "generate-downloadable-excel": {
        "title": "Generate Excel for Downloadable",
        "description": "Filter a Media Inventory for PDF, Word and PowerPoint "
                       "documents and export the audit rows.",
        "accent": "#7c3aed",
        "endpoint": "/api/feature/downloadable",
        "multiple": False, "accept": ".xlsx,.xls,.csv",
        "cta": "Generate Document List",
        "input_label": "Upload a media inventory workbook",
        "need_sheet": False, "need_parent_id": True,
    },
}


def render_operation(slug: str):
    op = OPERATIONS.get(slug)
    if not op:
        abort(404)
    return render_template("operation.html", slug=slug,
                           template_found=feature_service.WCAG_TEMPLATE.exists(),
                           **op)
