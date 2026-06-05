"""Validation engine: missing values, blank rows, duplicates, format checks."""
from __future__ import annotations

import re
from typing import Any

import polars as pl

from utils.helpers import ID_COL, data_columns

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_RE = r"^[+]?[\d\s().-]{7,}$"
DATE_RE = r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$"
NUMBER_RE = r"^-?\d+(\.\d+)?$"


def _str(col: str) -> pl.Expr:
    return pl.col(col).cast(pl.Utf8, strict=False)


def validate(df: pl.DataFrame, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the full validation suite. Returns a structured report."""
    rules = rules or {}
    cols = data_columns(df)
    total = df.height

    issues: list[dict[str, Any]] = []

    # missing values per column — counts nulls AND empty/whitespace-only
    # strings, so the number matches the blue-highlighted cells everywhere.
    from utils.helpers import missing_expr
    missing_by_col = {}
    for c in cols:
        n = int(df.select(missing_expr(c).sum()).item())
        missing_by_col[c] = n
        if n:
            issues.append({"type": "Missing values", "column": c, "count": n})

    # blank rows (all data columns null/empty)
    blank_expr = pl.all_horizontal([
        (pl.col(c).is_null() | (_str(c).str.strip_chars() == "")) for c in cols
    ]) if cols else pl.lit(False)
    blank_rows = int(df.select(blank_expr.sum()).item()) if cols else 0
    if blank_rows:
        issues.append({"type": "Blank rows", "column": "(row)", "count": blank_rows})

    # duplicate rows (full)
    dup_rows = total - df.select(cols).unique().height if cols else 0
    if dup_rows:
        issues.append({"type": "Duplicate rows", "column": "(all)", "count": dup_rows})

    # format checks, auto-detected by column-name hints + value sampling
    fmt_rules = rules.get("formats") or _auto_format_rules(df, cols)
    for col, kind in fmt_rules.items():
        if col not in df.columns:
            continue
        pat = {"email": EMAIL_RE, "phone": PHONE_RE,
               "date": DATE_RE, "number": NUMBER_RE}.get(kind)
        if not pat:
            continue
        non_null = df.filter(pl.col(col).is_not_null()
                             & (_str(col).str.strip_chars() != ""))
        bad = non_null.filter(~_str(col).str.contains(pat))
        if bad.height:
            issues.append({
                "type": f"Invalid {kind}", "column": col, "count": bad.height,
            })

    score = 100.0
    if total:
        total_missing = sum(missing_by_col.values())
        cells = total * max(1, len(cols))
        penalty = (total_missing / cells) * 40 + (dup_rows / total) * 30 + \
                  (blank_rows / total) * 30
        score = max(0.0, round(100 - penalty, 1))

    return {
        "total_rows": total,
        "total_columns": len(cols),
        "missing_by_col": missing_by_col,
        "blank_rows": blank_rows,
        "duplicate_rows": dup_rows,
        "issues": issues,
        "issue_count": int(sum(i["count"] for i in issues)),
        "quality_score": score,
        "detected_formats": fmt_rules,
    }


def error_rows(df: pl.DataFrame, rules: dict[str, Any] | None = None,
               limit: int = 500) -> list[dict[str, Any]]:
    """Return rows that fail any format/blank check, with a reason column."""
    rules = rules or {}
    cols = data_columns(df)
    fmt_rules = rules.get("formats") or _auto_format_rules(df, cols)
    flagged: dict[int, list[str]] = {}

    for col, kind in fmt_rules.items():
        pat = {"email": EMAIL_RE, "phone": PHONE_RE,
               "date": DATE_RE, "number": NUMBER_RE}.get(kind)
        if not pat or col not in df.columns:
            continue
        bad = df.filter(
            pl.col(col).is_not_null()
            & (_str(col).str.strip_chars() != "")
            & ~_str(col).str.contains(pat)
        )
        for rid in bad.get_column(ID_COL).to_list():
            flagged.setdefault(rid, []).append(f"Invalid {kind}: {col}")

    if not flagged:
        return []
    subset = df.filter(pl.col(ID_COL).is_in(list(flagged.keys()))).head(limit)
    from utils.helpers import rows_to_records
    out = rows_to_records(subset)
    for rec in out:
        rec["__reason"] = "; ".join(flagged.get(rec[ID_COL], []))
    return out


def _auto_format_rules(df: pl.DataFrame, cols: list[str]) -> dict[str, str]:
    """Guess which columns should be email/phone/date based on names."""
    rules: dict[str, str] = {}
    for c in cols:
        low = c.lower()
        if "email" in low or "e-mail" in low:
            rules[c] = "email"
        elif "phone" in low or "mobile" in low or "contact" in low:
            rules[c] = "phone"
        elif low in ("date", "dob") or low.endswith("_date") or "date" in low:
            rules[c] = "date"
    return rules
