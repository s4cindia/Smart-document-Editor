"""Smart Editor routes.

Blueprints (names + URL prefixes preserved from the original app so existing
front-end calls keep working):
    files_bp      /api/files       open / sheets / load / recent / folder
    data_bp       /api/data        columns / rows / edits / undo-redo
    check_bp      /api             validate / duplicates
    transform_bp  /api/transform   bulk transforms (+ preview)
    analytics_bp  /api/analytics   overview / statistics / profile / chart
    export_bp     /api             export / report
    pdf_bp        /api/pdf         info / text / search / tables
"""
from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, request

from app_helpers import (fail, load_pdf, load_tabular, ok, pdf_info_payload,
                         status_payload)
from config import config
from services import excel_service, export_service
from services.store import FileMeta, store
from smart_editor import services as editor_services
from smart_editor import validators
from utils import file_utils
from utils.helpers import ID_COL, column_defs, data_columns

log = logging.getLogger("sde.smart_editor")

files_bp = Blueprint("files", __name__, url_prefix="/api/files")
data_bp = Blueprint("data", __name__, url_prefix="/api/data")
check_bp = Blueprint("check", __name__, url_prefix="/api")
transform_bp = Blueprint("transform", __name__, url_prefix="/api/transform")
analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")
export_bp = Blueprint("export", __name__, url_prefix="/api")
pdf_bp = Blueprint("pdf", __name__, url_prefix="/api/pdf")


# --------------------------------------------------------------------------
# Files: open / sheets / load / recent / folder
# --------------------------------------------------------------------------
@files_bp.route("/open", methods=["POST"])
def open_file():
    if "file" not in request.files:
        return fail("No file part in request.")
    f = request.files["file"]
    if not f.filename:
        return fail("No file selected.")
    if not file_utils.allowed_file(f.filename):
        return fail("Unsupported file type.")
    dest = file_utils.unique_path(config.upload_dir,
                                  file_utils.safe_filename(f.filename))
    f.save(dest)
    ext = dest.suffix.lower()

    try:
        if ext in (".xlsx", ".xls"):
            sheets = excel_service.list_sheets(dest)
            if len(sheets) > 1:
                return ok(needs_sheet=True, path=str(dest), sheets=sheets,
                          name=dest.name)
            load_tabular(dest, sheets[0] if sheets else None)
            return ok(loaded=True, status=status_payload())

        if ext == ".pdf":
            load_pdf(dest)
            return ok(loaded=True, pdf=True, status=status_payload(),
                      pdf_info=pdf_info_payload())

        load_tabular(dest)
        return ok(loaded=True, status=status_payload())
    except Exception as exc:  # noqa: BLE001
        log.exception("open failed: %s", dest.name)
        return fail(f"“{dest.name}” could not be opened. The file may be "
                    f"corrupt, empty, or not a valid {ext.lstrip('.') or 'data'} "
                    f"file. Details: {exc}")


@files_bp.route("/open-path", methods=["POST"])
def open_path():
    body = request.get_json(force=True, silent=True) or {}
    path = Path(body.get("path", "")).expanduser()
    if not path.exists():
        return fail("File not found.")
    ext = path.suffix.lower()
    if ext == ".pdf":
        load_pdf(path)
        return ok(loaded=True, pdf=True, status=status_payload(),
                  pdf_info=pdf_info_payload())
    if ext in (".xlsx", ".xls"):
        sheets = excel_service.list_sheets(path)
        if len(sheets) > 1:
            return ok(needs_sheet=True, path=str(path), sheets=sheets,
                      name=path.name)
        load_tabular(path, sheets[0] if sheets else None)
        return ok(loaded=True, status=status_payload())
    load_tabular(path)
    return ok(loaded=True, status=status_payload())


@files_bp.route("/sheets")
def sheets():
    path = request.args.get("path", "")
    if not path:
        return fail("Missing path.")
    return ok(sheets=excel_service.list_sheets(path))


@files_bp.route("/load-sheet", methods=["POST"])
def load_sheet():
    body = request.get_json(force=True, silent=True) or {}
    path = body.get("path")
    sheet = body.get("sheet")
    if not path:
        return fail("Missing path.")
    load_tabular(Path(path), sheet)
    return ok(loaded=True, status=status_payload())


@files_bp.route("/recent")
def recent():
    return ok(recent=file_utils.load_recent())


@files_bp.route("/folder", methods=["POST"])
def folder():
    body = request.get_json(force=True, silent=True) or {}
    items = file_utils.list_folder(body.get("folder", ""))
    return ok(items=items)


# --------------------------------------------------------------------------
# Grid data: columns / rows (infinite model) / edits / undo-redo
# --------------------------------------------------------------------------
@data_bp.route("/columns")
def columns():
    if not store.loaded:
        return ok(columns=[])
    return ok(columns=column_defs(store.df), names=data_columns(store.df))


@data_bp.route("/rows", methods=["POST"])
def rows():
    if not store.loaded:
        return ok(rows=[], lastRow=0)
    body = request.get_json(force=True, silent=True) or {}
    start = int(body.get("startRow", 0))
    end = int(body.get("endRow", config.page_size_default))
    end = min(end, start + config.page_size_max)
    page = store.query_page(
        start, end,
        sort_model=body.get("sortModel"),
        search=body.get("search"),
        search_columns=body.get("searchColumns"),
        search_mode=body.get("searchMode", "contains"),
    )
    return ok(**page)


@data_bp.route("/cell", methods=["POST"])
def update_cell():
    body = request.get_json(force=True, silent=True) or {}
    try:
        store.update_cell(int(body["id"]), body["field"], body.get("value"))
    except (KeyError, ValueError) as exc:
        return fail(str(exc))
    return ok(status=status_payload())


@data_bp.route("/add-row", methods=["POST"])
def add_row():
    if not store.loaded:
        return fail("No dataset loaded.")
    new_id = store.add_row()
    return ok(id=new_id, status=status_payload())


@data_bp.route("/delete-rows", methods=["POST"])
def delete_rows():
    body = request.get_json(force=True, silent=True) or {}
    ids = [int(i) for i in body.get("ids", [])]
    if not ids:
        return fail("No rows selected.")
    removed = store.delete_rows(ids)
    return ok(removed=removed, status=status_payload())


@data_bp.route("/duplicate-rows", methods=["POST"])
def duplicate_rows():
    body = request.get_json(force=True, silent=True) or {}
    ids = [int(i) for i in body.get("ids", [])]
    if not ids:
        return fail("No rows selected.")
    added = store.duplicate_rows(ids)
    return ok(added=added, status=status_payload())


@data_bp.route("/undo", methods=["POST"])
def undo():
    desc = store.undo()
    if desc is None:
        return fail("Nothing to undo.")
    return ok(description=desc, status=status_payload())


@data_bp.route("/redo", methods=["POST"])
def redo():
    desc = store.redo()
    if desc is None:
        return fail("Nothing to redo.")
    return ok(description=desc, status=status_payload())


# --------------------------------------------------------------------------
# Check: validation + duplicates
# --------------------------------------------------------------------------
@check_bp.route("/validate", methods=["POST"])
def validate():
    if not store.loaded:
        return fail("No dataset loaded.")
    body = request.get_json(force=True, silent=True) or {}
    report = validators.validate(store.df, body.get("rules"))
    return ok(report=report)


@check_bp.route("/validate/errors")
def validate_errors():
    if not store.loaded:
        return fail("No dataset loaded.")
    rows_ = validators.error_rows(store.df)
    return ok(rows=rows_, count=len(rows_))


@check_bp.route("/duplicates", methods=["POST"])
def duplicates():
    if not store.loaded:
        return fail("No dataset loaded.")
    body = request.get_json(force=True, silent=True) or {}
    result = validators.find_duplicates(store.df, body.get("columns"))
    # Group matching rows together: bring duplicate rows to the top, ordered by
    # group, so members of the same group are adjacent in the grid.
    dup_ids = result.get("duplicate_ids") or []
    if dup_ids:
        store.reorder_by_ids(dup_ids)
    return ok(result=result, regrouped=bool(dup_ids))


@check_bp.route("/duplicates/drop", methods=["POST"])
def drop_duplicates():
    if not store.loaded:
        return fail("No dataset loaded.")
    body = request.get_json(force=True, silent=True) or {}
    new_df = validators.drop_duplicates(store.df, body.get("columns"))
    removed = store.df.height - new_df.height
    store.apply(new_df, "Drop duplicates")
    return ok(removed=removed, status=status_payload())


# --------------------------------------------------------------------------
# Transform / bulk edit (single dispatch endpoint, supports preview)
# --------------------------------------------------------------------------
@transform_bp.route("/<op>", methods=["POST"])
def transform(op: str):
    if not store.loaded:
        return fail("No dataset loaded.")
    if op not in editor_services.TRANSFORMS:
        return fail(f"Unknown transform: {op}", 404)
    body = request.get_json(force=True, silent=True) or {}
    try:
        new_df, desc = editor_services.TRANSFORMS[op](store.df, body)
    except Exception as exc:  # noqa: BLE001
        return fail(f"Transform failed: {exc}")

    if body.get("preview"):
        prev = editor_services.transform_preview(store.df, new_df, body.get("columns"))
        return ok(preview=prev, description=desc)

    store.apply(new_df, desc)
    return ok(description=desc, status=status_payload())


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------
@analytics_bp.route("/overview")
def an_overview():
    if not store.loaded:
        return fail("No dataset loaded.")
    return ok(overview=editor_services.analytics().overview(store.df))


@analytics_bp.route("/statistics")
def an_statistics():
    if not store.loaded:
        return fail("No dataset loaded.")
    return ok(statistics=editor_services.analytics().statistics(store.df))


@analytics_bp.route("/profile")
def an_profile():
    if not store.loaded:
        return fail("No dataset loaded.")
    return ok(profile=editor_services.analytics().column_profile(store.df))


@analytics_bp.route("/chart")
def an_chart():
    if not store.loaded:
        return fail("No dataset loaded.")
    column = request.args.get("column")
    if column:
        return ok(chart=editor_services.analytics().frequency(store.df, column))
    return ok(chart=editor_services.analytics().chart_data(store.df))


# --------------------------------------------------------------------------
# Export + reports
# --------------------------------------------------------------------------
@export_bp.route("/export/<fmt>", methods=["POST"])
def export(fmt: str):
    if not store.loaded:
        return fail("No dataset loaded.")
    stem = Path(store.meta.name).stem or "export"
    try:
        if fmt == "excel":
            body = request.get_json(silent=True) or {}
            # Two independent, optional highlights:
            #   • blank/empty cells in blue  (written by the xlsx writer)
            #   • long / multi-line Summary cells in yellow (post-processed)
            hl_blanks = bool(body.get("highlight_blanks"))
            hl_summary = bool(body.get("highlight_summary") or body.get("highlight"))
            path = editor_services.export(store.df, "excel", stem, highlight=hl_blanks)
            if hl_summary:
                from services.excel_service import highlight_summary_cells
                highlight_summary_cells(path)
        elif fmt in ("csv", "json", "pdf"):
            path = editor_services.export(store.df, fmt, stem)
        else:
            return fail(f"Unsupported export format: {fmt}", 404)
    except Exception as exc:  # noqa: BLE001
        log.exception("export failed")
        return fail(f"Export failed: {exc}")
    return ok(file=path.name, url=f"/download/exports/{path.name}",
              rows=store.df.height, cols=len(data_columns(store.df)))


@export_bp.route("/report/<kind>/<fmt>", methods=["POST"])
def report(kind: str, fmt: str):
    if not store.loaded:
        return fail("No dataset loaded.")
    if kind not in ("validation", "duplicate", "error", "summary"):
        return fail("Unknown report kind.", 404)
    try:
        path = editor_services.report(store.df, kind, fmt)
    except Exception as exc:  # noqa: BLE001
        log.exception("report failed")
        return fail(f"Report failed: {exc}")
    return ok(file=path.name, url=f"/download/reports/{path.name}")


# --------------------------------------------------------------------------
# PDF module
# --------------------------------------------------------------------------
@pdf_bp.route("/info")
def pdf_info():
    if store.meta.source != "pdf":
        return fail("No PDF loaded.")
    return ok(pdf_info=pdf_info_payload())


@pdf_bp.route("/text")
def pdf_text():
    if store.meta.source != "pdf":
        return fail("No PDF loaded.")
    page = request.args.get("page", type=int)
    pages = store.extra.get("text", [])
    if page:
        match = next((p for p in pages if p["page"] == page), None)
        return ok(text=match)
    return ok(pages=pages)


@pdf_bp.route("/search", methods=["POST"])
def pdf_search():
    if store.meta.source != "pdf":
        return fail("No PDF loaded.")
    from services import pdf_service
    body = request.get_json(force=True, silent=True) or {}
    term = body.get("term", "")
    if not term:
        return fail("Missing search term.")
    hits = pdf_service.search_text(store.extra.get("text", []), term)
    return ok(hits=hits, count=len(hits))


@pdf_bp.route("/load-table", methods=["POST"])
def pdf_load_table():
    if store.meta.source != "pdf":
        return fail("No PDF loaded.")
    body = request.get_json(force=True, silent=True) or {}
    page = int(body.get("page", -1))
    index = int(body.get("index", -1))
    tables = store.extra.get("tables", [])
    match = next((t for t in tables if t["page"] == page and t["index"] == index),
                 None)
    if match is None:
        return fail("Table not found.")
    extra = store.extra
    src_path = store.meta.path
    src_name = store.meta.name
    store.set_dataframe(match["frame"], FileMeta(
        path=src_path, name=f"{src_name} (p{page} t{index+1})",
        ext=".pdf", source="pdf-table"))
    store.extra = extra  # keep pdf payload so user can pick other tables
    return ok(loaded=True, status=status_payload())


@pdf_bp.route("/export-table", methods=["POST"])
def pdf_export_table():
    if store.meta.source not in ("pdf", "pdf-table"):
        return fail("No PDF loaded.")
    body = request.get_json(force=True, silent=True) or {}
    page = int(body.get("page", -1))
    index = int(body.get("index", -1))
    fmt = body.get("format", "excel")
    tables = store.extra.get("tables", [])
    match = next((t for t in tables if t["page"] == page and t["index"] == index),
                 None)
    if match is None:
        return fail("Table not found.")
    frame = match["frame"]
    stem = f"pdf_p{page}_t{index+1}"
    if fmt == "csv":
        path = export_service.export_csv(frame, stem)
    else:
        path = export_service.export_excel(frame, stem)
    return ok(file=path.name, url=f"/download/exports/{path.name}")
