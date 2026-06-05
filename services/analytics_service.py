"""Analytics: dataset stats, per-column profile, chart-ready aggregations."""
from __future__ import annotations

from typing import Any

import polars as pl

from utils.helpers import ID_COL, data_columns


def overview(df: pl.DataFrame) -> dict[str, Any]:
    from utils.helpers import missing_expr
    cols = data_columns(df)
    total_missing = 0
    dtype_counts: dict[str, int] = {}
    for c in cols:
        total_missing += int(df.select(missing_expr(c).sum()).item())
        t = _friendly_type(df.schema[c])
        dtype_counts[t] = dtype_counts.get(t, 0) + 1
    dup_rows = df.height - df.select(cols).unique().height if cols else 0
    return {
        "total_rows": df.height,
        "total_columns": len(cols),
        "missing_values": total_missing,
        "duplicate_rows": dup_rows,
        "type_summary": dtype_counts,
        "memory": f"{df.estimated_size('mb'):.2f} MB",
    }


def column_profile(df: pl.DataFrame) -> list[dict[str, Any]]:
    cols = data_columns(df)
    out: list[dict[str, Any]] = []
    from utils.helpers import missing_expr
    for c in cols:
        s = df.get_column(c)
        dtype = df.schema[c]
        nulls = int(df.select(missing_expr(c).sum()).item())
        unique = int(s.n_unique())
        entry: dict[str, Any] = {
            "column": c,
            "type": _friendly_type(dtype),
            "nulls": nulls,
            "null_pct": round(100 * nulls / df.height, 1) if df.height else 0,
            "unique": unique,
        }
        if dtype in pl.NUMERIC_DTYPES:
            entry.update({
                "min": _num(s.min()),
                "max": _num(s.max()),
                "mean": _num(s.mean()),
                "median": _num(s.median()),
                "std": _num(s.std()),
            })
        else:
            top = (df.group_by(c).len().sort("len", descending=True).head(1))
            if top.height:
                entry["top"] = _safe(top.row(0)[0])
                entry["top_count"] = int(top.row(0)[1])
        out.append(entry)
    return out


def statistics(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Numeric describe()-style stats per numeric column."""
    cols = [c for c in data_columns(df) if df.schema[c] in pl.NUMERIC_DTYPES]
    rows = []
    for c in cols:
        s = df.get_column(c)
        rows.append({
            "column": c,
            "count": int(s.len() - s.is_null().sum()),
            "min": _num(s.min()),
            "max": _num(s.max()),
            "mean": _num(s.mean()),
            "median": _num(s.median()),
            "std": _num(s.std()),
            "sum": _num(s.sum()),
        })
    return rows


def frequency(df: pl.DataFrame, column: str, top: int = 12) -> dict[str, Any]:
    if column not in df.columns:
        return {"column": column, "labels": [], "values": []}
    vc = (df.group_by(column).len().rename({"len": "count"})
          .sort("count", descending=True).head(top))
    return {
        "column": column,
        "labels": [_safe(v) for v in vc.get_column(column).to_list()],
        "values": vc.get_column("count").to_list(),
    }


def chart_data(df: pl.DataFrame) -> dict[str, Any]:
    """Pick a sensible default chart: frequency of first low-cardinality column."""
    cols = data_columns(df)
    target = None
    for c in cols:
        if 1 < df.get_column(c).n_unique() <= 30:
            target = c
            break
    if target is None and cols:
        target = cols[0]
    if target is None:
        return {"column": None, "labels": [], "values": []}
    return frequency(df, target)


def _friendly_type(dtype: pl.DataType) -> str:
    if dtype in pl.INTEGER_DTYPES:
        return "Integer"
    if dtype in pl.FLOAT_DTYPES:
        return "Float"
    if dtype == pl.Boolean:
        return "Boolean"
    if dtype in (pl.Date, pl.Datetime, pl.Time):
        return "Date/Time"
    return "Text"


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _safe(value: Any) -> Any:
    if value is None:
        return "(null)"
    return str(value)
