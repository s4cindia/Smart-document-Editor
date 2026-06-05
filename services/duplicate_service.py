"""Duplicate detection: full-row, single-column, and multi-column."""
from __future__ import annotations

from typing import Any

import polars as pl

from utils.helpers import ID_COL, data_columns, rows_to_records


def find_duplicates(df: pl.DataFrame, columns: list[str] | None = None,
                    limit: int = 1000) -> dict[str, Any]:
    """Find duplicate rows based on *columns* (defaults to all data columns).

    Returns the duplicate group ids, the affected row records, and a count.
    """
    cols = columns or data_columns(df)
    cols = [c for c in cols if c in df.columns and c != ID_COL]
    if not cols or df.height == 0:
        return {"columns": cols, "group_count": 0, "duplicate_rows": 0, "rows": []}

    # mark rows whose key appears more than once
    keyed = df.with_columns(
        pl.struct(cols).alias("__key")
    )
    counts = keyed.group_by("__key").len().rename({"len": "__n"})
    dup_keys = counts.filter(pl.col("__n") > 1)
    group_count = dup_keys.height

    flagged = keyed.join(dup_keys.select("__key", "__n"), on="__key", how="inner")
    # assign a stable group number
    group_ids = (
        flagged.select("__key").unique(maintain_order=True)
        .with_row_index("__group")
    )
    flagged = flagged.join(group_ids, on="__key", how="left")
    flagged = flagged.sort("__group").drop("__key")

    total_dups = flagged.height
    show = flagged.head(limit)
    records = rows_to_records(show.drop("__n"))
    # __group already JSON-safe (int)
    return {
        "columns": cols,
        "group_count": group_count,
        "duplicate_rows": total_dups,
        "rows": records,
        "duplicate_ids": flagged.get_column(ID_COL).to_list(),
    }


def column_value_duplicates(df: pl.DataFrame, column: str,
                            limit: int = 200) -> dict[str, Any]:
    """Return values in *column* that appear more than once, with counts."""
    if column not in df.columns:
        return {"column": column, "values": []}
    vc = (
        df.group_by(column).len().rename({"len": "count"})
        .filter(pl.col("count") > 1)
        .sort("count", descending=True)
        .head(limit)
    )
    return {"column": column, "values": rows_to_records(vc)}


def drop_duplicates(df: pl.DataFrame, columns: list[str] | None = None) -> pl.DataFrame:
    """Return a frame with duplicate rows removed (keeping first occurrence)."""
    cols = columns or data_columns(df)
    cols = [c for c in cols if c in df.columns and c != ID_COL]
    if not cols:
        return df
    return df.unique(subset=cols, keep="first", maintain_order=True)
