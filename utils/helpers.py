"""Helpers for converting between Polars frames and JSON-safe structures."""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any

import polars as pl

ID_COL = "__id"


def is_missing(value: Any) -> bool:
    """True if a value should count as missing/blank.

    Missing = None, NaN, or an empty/whitespace-only string. Used for both
    the on-open grid highlight and the highlighted export.
    """
    if value is None:
        return True
    if isinstance(value, float):
        try:
            return math.isnan(value)
        except (TypeError, ValueError):
            return False
    if isinstance(value, str):
        return value.strip() == ""
    return False


def missing_expr(col: str) -> pl.Expr:
    """Polars expression that is True where a cell is missing/blank.

    Mirrors is_missing(): null, or empty/whitespace-only string. Keeps the
    missing-value count consistent with the blue highlighting in the grid
    and in exports.
    """
    s = pl.col(col).cast(pl.Utf8, strict=False).str.strip_chars()
    return pl.col(col).is_null() | (s == "")


def json_safe(value: Any) -> Any:
    """Make a single cell value safe for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return str(value)
    return value


def rows_to_records(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Convert a Polars frame to a list of JSON-safe record dicts."""
    records = df.to_dicts()
    out: list[dict[str, Any]] = []
    for rec in records:
        out.append({k: json_safe(v) for k, v in rec.items()})
    return out


def infer_grid_type(dtype: pl.DataType) -> str:
    """Map a Polars dtype to an AG Grid cell data type string."""
    if dtype in pl.NUMERIC_DTYPES:
        return "number"
    if dtype == pl.Boolean:
        return "boolean"
    if dtype in (pl.Date, pl.Datetime, pl.Time):
        return "date"
    return "text"


def column_defs(df: pl.DataFrame, visible_id: bool = False) -> list[dict[str, Any]]:
    """Build AG Grid column definitions from a frame's schema."""
    defs: list[dict[str, Any]] = []
    for name, dtype in df.schema.items():
        if name == ID_COL and not visible_id:
            continue
        defs.append({
            "field": name,
            "headerName": name,
            "dataType": infer_grid_type(dtype),
            "polarsType": str(dtype),
        })
    return defs


def data_columns(df: pl.DataFrame) -> list[str]:
    """Column names excluding the internal id column."""
    return [c for c in df.columns if c != ID_COL]
