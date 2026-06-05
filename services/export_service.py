"""Export data (Excel/CSV/JSON/PDF) and generate reports (PDF/Excel/HTML)."""
from __future__ import annotations

import datetime as _dt
import html
import json
from pathlib import Path
from typing import Any

import polars as pl

from config import config
from services import analytics_service, validation_service
from services.excel_service import write_excel
from utils.helpers import data_columns, rows_to_records

_TS = lambda: _dt.datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: E731


def _outpath(folder: Path, stem: str, ext: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stem}_{_TS()}{ext}"
    # avoid collisions when two exports happen in the same second
    n = 2
    while path.exists():
        path = folder / f"{stem}_{_TS()}_{n}{ext}"
        n += 1
    return path


def _clean_frame(df: pl.DataFrame) -> pl.DataFrame:
    """Drop the internal id column for user-facing exports."""
    from utils.helpers import ID_COL
    return df.drop(ID_COL) if ID_COL in df.columns else df


# -- data exports -----------------------------------------------------------

def export_excel(df: pl.DataFrame, stem: str = "export", highlight: bool = True) -> Path:
    from services.excel_service import write_excel, write_excel_highlighted
    out = _outpath(config.export_dir, stem, ".xlsx")
    clean = _clean_frame(df)
    if highlight:
        return write_excel_highlighted(clean, out)
    return write_excel(clean, out)


def export_csv(df: pl.DataFrame, stem: str = "export", separator: str = ",") -> Path:
    out = _outpath(config.export_dir, stem, ".csv")
    _clean_frame(df).write_csv(out, separator=separator)
    return out


def export_json(df: pl.DataFrame, stem: str = "export") -> Path:
    out = _outpath(config.export_dir, stem, ".json")
    records = rows_to_records(_clean_frame(df))
    out.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    return out


def export_pdf(df: pl.DataFrame, stem: str = "export") -> Path:
    """Export the FULL dataset as a PDF table.

    Every row and column is included (no truncation). Missing/blank cells are
    highlighted with a blue background to match the Excel export.
    """
    from utils.helpers import is_missing
    clean = _clean_frame(df)
    cols = clean.columns
    body_rows = "".join(
        "<tr>" + "".join(
            (f"<td class='miss'></td>" if is_missing(v)
             else f"<td>{html.escape(str(v))}</td>")
            for v in row) + "</tr>"
        for row in clean.iter_rows()
    )
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = f"""
      <h1>Data Export</h1>
      <p class='meta'>{clean.height} rows &middot; {len(cols)} columns
        &middot; missing values highlighted in blue</p>
      <table><thead><tr>{head}</tr></thead><tbody>{body_rows}</tbody></table>
    """
    out = _outpath(config.export_dir, stem, ".pdf")
    _html_to_pdf(body, out, landscape=True, n_cols=len(cols))
    return out


# -- reports ----------------------------------------------------------------

def _report_body(df: pl.DataFrame, kind: str) -> str:
    title = {
        "validation": "Validation Report",
        "duplicate": "Duplicate Report",
        "error": "Error Report",
        "summary": "Data Summary Report",
    }.get(kind, "Report")

    parts = [f"<h1>{title}</h1>",
             f"<p class='meta'>Generated {_dt.datetime.now():%Y-%m-%d %H:%M} "
             f"&middot; {df.height} rows &middot; {len(data_columns(df))} columns</p>"]

    if kind in ("validation", "error"):
        rep = validation_service.validate(df)
        parts.append(f"<div class='score'>Data quality score: "
                     f"<b>{rep['quality_score']}/100</b></div>")
        parts.append(_kv_table({
            "Total rows": rep["total_rows"],
            "Total columns": rep["total_columns"],
            "Blank rows": rep["blank_rows"],
            "Duplicate rows": rep["duplicate_rows"],
            "Total issues": rep["issue_count"],
        }))
        parts.append("<h2>Issues</h2>")
        parts.append(_issue_table(rep["issues"]))
        parts.append("<h2>Missing values by column</h2>")
        parts.append(_kv_table({k: v for k, v in rep["missing_by_col"].items() if v}))

    if kind == "duplicate":
        from services.duplicate_service import find_duplicates
        dup = find_duplicates(df, limit=200)
        parts.append(_kv_table({
            "Duplicate groups": dup["group_count"],
            "Duplicate rows": dup["duplicate_rows"],
            "Key columns": ", ".join(dup["columns"]),
        }))

    if kind == "summary":
        ov = analytics_service.overview(df)
        parts.append(_kv_table({
            "Total rows": ov["total_rows"],
            "Total columns": ov["total_columns"],
            "Missing values": ov["missing_values"],
            "Duplicate rows": ov["duplicate_rows"],
            "Memory": ov["memory"],
        }))
        parts.append("<h2>Column profile</h2>")
        parts.append(_profile_table(analytics_service.column_profile(df)))

    # full dataset — every row and column, missing cells highlighted blue
    parts.append("<h2>Full data</h2>")
    parts.append(_data_table(df))

    return "".join(parts)


def _data_table(df: pl.DataFrame) -> str:
    """Render the complete dataset as an HTML table (all rows + columns)."""
    from utils.helpers import is_missing
    clean = _clean_frame(df)
    cols = clean.columns
    if not cols:
        return "<p class='note'>No columns.</p>"
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body_rows = "".join(
        "<tr>" + "".join(
            ("<td class='miss'></td>" if is_missing(v)
             else f"<td>{html.escape(str(v))}</td>")
            for v in row) + "</tr>"
        for row in clean.iter_rows()
    )
    return (f"<table class='data'><thead><tr>{head}</tr></thead>"
            f"<tbody>{body_rows}</tbody></table>")


def generate_report(df: pl.DataFrame, kind: str, fmt: str) -> Path:
    stem = f"{kind}_report"
    if fmt == "html":
        out = _outpath(config.report_dir, stem, ".html")
        out.write_text(_html_doc(_report_body(df, kind)), encoding="utf-8")
        return out
    if fmt == "pdf":
        out = _outpath(config.report_dir, stem, ".pdf")
        n_cols = len(data_columns(df))
        _html_to_pdf(_report_body(df, kind), out, landscape=True, n_cols=n_cols)
        return out
    if fmt == "excel":
        return _report_excel(df, kind, stem)
    raise ValueError(f"Unsupported report format: {fmt}")


def _report_excel(df: pl.DataFrame, kind: str, stem: str) -> Path:
    out = _outpath(config.report_dir, stem, ".xlsx")
    sheets: dict[str, pl.DataFrame] = {}
    if kind in ("validation", "error"):
        rep = validation_service.validate(df)
        sheets["Summary"] = pl.DataFrame({
            "metric": ["Quality score", "Total rows", "Total columns",
                       "Blank rows", "Duplicate rows", "Total issues"],
            "value": [rep["quality_score"], rep["total_rows"], rep["total_columns"],
                      rep["blank_rows"], rep["duplicate_rows"], rep["issue_count"]],
        })
        if rep["issues"]:
            sheets["Issues"] = pl.DataFrame(rep["issues"])
    elif kind == "summary":
        sheets["Overview"] = pl.DataFrame([analytics_service.overview(df)]).unnest("type_summary") \
            if False else pl.DataFrame({
                "metric": list(analytics_service.overview(df).keys()),
                "value": [str(v) for v in analytics_service.overview(df).values()],
            })
        sheets["Profile"] = pl.DataFrame(analytics_service.column_profile(df))
    elif kind == "duplicate":
        from services.duplicate_service import find_duplicates
        dup = find_duplicates(df, limit=5000)
        sheets["Summary"] = pl.DataFrame({
            "metric": ["Duplicate groups", "Duplicate rows", "Key columns"],
            "value": [dup["group_count"], dup["duplicate_rows"],
                      ", ".join(dup["columns"])],
        })
        if dup["rows"]:
            sheets["Duplicates"] = pl.DataFrame(dup["rows"])

    import xlsxwriter
    with xlsxwriter.Workbook(str(out)) as wb:
        header_fmt = wb.add_format({"bold": True, "bg_color": "#2563eb",
                                    "font_color": "#ffffff"})
        for name, sheet_df in (sheets or {"Report": pl.DataFrame()}).items():
            ws = wb.add_worksheet(name[:31])
            cols = sheet_df.columns
            for j, col in enumerate(cols):
                ws.write(0, j, col, header_fmt)
            for i, row in enumerate(sheet_df.iter_rows(), start=1):
                for j, val in enumerate(row):
                    ws.write(i, j, "" if val is None else str(val))
    return out


# -- HTML / PDF rendering ---------------------------------------------------

_CSS = """
body{font-family:Helvetica,Arial,sans-serif;color:#1f2937;margin:18px;}
h1{color:#1d4ed8;font-size:22px;margin:0 0 4px;}
h2{color:#374151;font-size:15px;margin:16px 0 6px;border-bottom:1px solid #e5e7eb;padding-bottom:3px;}
.meta{color:#6b7280;font-size:11px;margin:0 0 12px;}
.note{color:#b45309;font-size:11px;}
.score{background:#eff6ff;border:1px solid #bfdbfe;padding:8px 12px;border-radius:6px;
  font-size:13px;margin:8px 0;}
table{border-collapse:collapse;width:auto;max-width:760px;font-size:10px;margin:6px 0;}
table.data{width:100%;max-width:none;table-layout:fixed;}
thead{display:table-header-group;}
tr{page-break-inside:avoid;}
th{background:#2563eb;color:#fff;text-align:left;padding:5px 7px;
  border:1px solid #1e40af;word-wrap:break-word;overflow-wrap:anywhere;}
td{border:1px solid #d1d5db;padding:4px 7px;vertical-align:top;
  word-wrap:break-word;overflow-wrap:anywhere;}
td.miss{background:#2563eb;border:1px solid #1e40af;}
tr:nth-child(even) td{background:#f9fafb;}
tr:nth-child(even) td.miss{background:#2563eb;}
table.data td{font-size:9.5px;}
"""


def _html_doc(body: str) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{_CSS}</style></head><body>{body}</body></html>")


def _html_to_pdf(body: str, out: Path, landscape: bool = False,
                 n_cols: int = 0) -> Path:
    """Render HTML to PDF.

    When *n_cols* is given, the page is widened so that every column fits at a
    readable width (PyMuPDF silently drops columns that can't meet a minimum
    width on a too-narrow page, which previously cut off wide tables).
    """
    import fitz  # PyMuPDF

    margin = 36
    if landscape:
        base_w, base_h = 842.0, 595.0   # A4 landscape
    else:
        base_w, base_h = 595.0, 842.0   # A4 portrait

    # widen the page to fit all columns (~78pt each + a little for borders)
    page_w = base_w
    if n_cols:
        needed = margin * 2 + n_cols * 78
        page_w = max(base_w, float(needed))

    html_doc = _html_doc(body)
    try:
        story = fitz.Story(html=html_doc)
        media = fitz.Rect(0, 0, page_w, base_h)
        content = media + (margin, margin, -margin, -margin)
        writer = fitz.DocumentWriter(str(out))
        more = 1
        while more:
            dev = writer.begin_page(media)
            more, _ = story.place(content)
            story.draw(dev)
            writer.end_page()
        writer.close()
        return out
    except Exception:  # noqa: BLE001 - fallback to plain text rendering
        return _text_pdf(body, out)


def _text_pdf(body: str, out: Path) -> Path:
    import re

    import fitz

    text = re.sub(r"<[^>]+>", "\n", body)
    text = html.unescape(re.sub(r"\n{2,}", "\n", text)).strip()
    doc = fitz.open()
    lines = text.splitlines()
    per_page = 55
    for start in range(0, max(1, len(lines)), per_page):
        page = doc.new_page()
        chunk = "\n".join(lines[start:start + per_page])
        page.insert_textbox(fitz.Rect(40, 40, 555, 800), chunk, fontsize=10)
    doc.save(str(out))
    doc.close()
    return out


def _kv_table(d: dict[str, Any]) -> str:
    if not d:
        return "<p class='note'>None.</p>"
    rows = "".join(f"<tr><td><b>{html.escape(str(k))}</b></td>"
                   f"<td>{html.escape(str(v))}</td></tr>" for k, v in d.items())
    return f"<table>{rows}</table>"


def _issue_table(issues: list[dict]) -> str:
    if not issues:
        return "<p class='note'>No issues detected.</p>"
    rows = "".join(f"<tr><td>{html.escape(str(i['type']))}</td>"
                   f"<td>{html.escape(str(i['column']))}</td>"
                   f"<td>{i['count']}</td></tr>" for i in issues)
    return f"<table><thead><tr><th>Type</th><th>Column</th><th>Count</th></tr></thead><tbody>{rows}</tbody></table>"


def _profile_table(profile: list[dict]) -> str:
    if not profile:
        return "<p class='note'>No columns.</p>"
    rows = "".join(
        f"<tr><td>{html.escape(str(p['column']))}</td><td>{p['type']}</td>"
        f"<td>{p['nulls']}</td><td>{p['unique']}</td></tr>" for p in profile)
    return ("<table><thead><tr><th>Column</th><th>Type</th><th>Nulls</th>"
            f"<th>Unique</th></tr></thead><tbody>{rows}</tbody></table>")
