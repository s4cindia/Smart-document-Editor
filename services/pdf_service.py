"""PDF text/table extraction and metadata via PDFPlumber + PyMuPDF."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl


def extract_metadata(path: str | Path) -> dict[str, Any]:
    """Return document metadata + page count using PyMuPDF."""
    import fitz  # PyMuPDF

    path = Path(path)
    doc = fitz.open(path)
    try:
        meta = dict(doc.metadata or {})
        meta["pages"] = doc.page_count
        meta["file_name"] = path.name
        return meta
    finally:
        doc.close()


def extract_text(path: str | Path) -> list[dict[str, Any]]:
    """Extract text per page. Returns [{page, text}]."""
    import fitz

    path = Path(path)
    doc = fitz.open(path)
    pages = []
    try:
        for i, page in enumerate(doc, start=1):
            pages.append({"page": i, "text": page.get_text("text")})
        return pages
    finally:
        doc.close()


def extract_tables(path: str | Path) -> list[dict[str, Any]]:
    """Extract tables using PDFPlumber.

    Returns a list of {page, index, columns, rows, frame} dicts where *frame*
    is a Polars DataFrame ready to load into the grid/export.
    """
    import pdfplumber

    path = Path(path)
    results: list[dict[str, Any]] = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for tindex, table in enumerate(tables):
                if not table or len(table) < 1:
                    continue
                header = [(_clean(c) or f"col_{j+1}") for j, c in enumerate(table[0])]
                header = _dedupe(header)
                body = table[1:] if len(table) > 1 else []
                norm_rows = []
                for r in body:
                    r = list(r) + [None] * (len(header) - len(r))
                    norm_rows.append({header[j]: _clean(r[j]) for j in range(len(header))})
                frame = pl.DataFrame(norm_rows, schema={h: pl.Utf8 for h in header}) \
                    if norm_rows else pl.DataFrame({h: [] for h in header})
                results.append({
                    "page": pno,
                    "index": tindex,
                    "columns": header,
                    "rows": len(norm_rows),
                    "frame": frame,
                })
    return results


def search_text(pages: list[dict[str, Any]], term: str) -> list[dict[str, Any]]:
    """Search already-extracted page text for *term* (case-insensitive)."""
    term_l = term.lower()
    hits = []
    for p in pages:
        text = p.get("text", "")
        low = text.lower()
        if term_l in low:
            count = low.count(term_l)
            idx = low.find(term_l)
            snippet = text[max(0, idx - 60): idx + 60].replace("\n", " ")
            hits.append({"page": p["page"], "count": count, "snippet": snippet})
    return hits


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).replace("\n", " ").strip()
    return s or None


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if n in seen:
            seen[n] += 1
            out.append(f"{n}_{seen[n]}")
        else:
            seen[n] = 0
            out.append(n)
    return out
