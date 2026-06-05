"""Central, single-user, in-memory data store.

Holds the currently loaded dataset as a Polars DataFrame, plus metadata,
undo/redo history, and server-side paging / sorting / filtering / search.

A stable internal id column (``__id``) gives every row a permanent identity
so the browser grid can edit/delete/duplicate rows safely even after sorting
or filtering.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import polars as pl

from config import config
from utils.helpers import ID_COL, column_defs, data_columns, rows_to_records


@dataclass
class FileMeta:
    path: str = ""
    name: str = "No file loaded"
    ext: str = ""
    size: str = ""
    sheet: str | None = None
    source: str = ""  # excel | csv | pdf


class DataStore:
    """Thread-safe holder for the active dataset."""

    def __init__(self) -> None:
        self._df: pl.DataFrame | None = None
        self.meta = FileMeta()
        self._undo: deque[tuple[pl.DataFrame, str]] = deque(maxlen=config.history_depth)
        self._redo: deque[tuple[pl.DataFrame, str]] = deque(maxlen=config.history_depth)
        self._next_id = 0
        self._lock = threading.RLock()
        # extra payloads kept around for PDF documents
        self.extra: dict[str, Any] = {}

    # -- loading ----------------------------------------------------------
    def set_dataframe(self, df: pl.DataFrame, meta: FileMeta) -> None:
        with self._lock:
            self._df = self._with_ids(df)
            self.meta = meta
            self._undo.clear()
            self._redo.clear()
            self.extra = {}

    def _with_ids(self, df: pl.DataFrame) -> pl.DataFrame:
        if ID_COL in df.columns:
            df = df.drop(ID_COL)
        n = df.height
        ids = pl.Series(ID_COL, range(n), dtype=pl.Int64)
        self._next_id = n
        # id first so it is easy to drop on export
        return df.insert_column(0, ids)

    def _new_ids(self, count: int) -> pl.Series:
        start = self._next_id
        self._next_id += count
        return pl.Series(ID_COL, range(start, start + count), dtype=pl.Int64)

    @property
    def loaded(self) -> bool:
        return self._df is not None

    @property
    def df(self) -> pl.DataFrame:
        if self._df is None:
            raise ValueError("No dataset is currently loaded.")
        return self._df

    # -- history ----------------------------------------------------------
    def _snapshot(self, description: str) -> None:
        if self._df is not None:
            self._undo.append((self._df.clone(), description))
            self._redo.clear()

    def undo(self) -> str | None:
        with self._lock:
            if not self._undo:
                return None
            df, desc = self._undo.pop()
            if self._df is not None:
                self._redo.append((self._df.clone(), desc))
            self._df = df
            return desc

    def redo(self) -> str | None:
        with self._lock:
            if not self._redo:
                return None
            df, desc = self._redo.pop()
            if self._df is not None:
                self._undo.append((self._df.clone(), desc))
            self._df = df
            return desc

    def can_undo(self) -> bool:
        return len(self._undo) > 0

    def can_redo(self) -> bool:
        return len(self._redo) > 0

    # -- mutation helper --------------------------------------------------
    def apply(self, new_df: pl.DataFrame, description: str) -> None:
        """Replace the frame, snapshotting the previous state for undo."""
        with self._lock:
            self._snapshot(description)
            self._df = new_df

    # -- paging / query ---------------------------------------------------
    def query_page(
        self,
        start: int,
        end: int,
        sort_model: list[dict] | None = None,
        search: str | None = None,
        search_columns: list[str] | None = None,
        search_mode: str = "contains",
    ) -> dict[str, Any]:
        """Return a page of rows for the AG Grid infinite row model."""
        with self._lock:
            if self._df is None:
                return {"rows": [], "lastRow": 0}
            df = self._df

            if search:
                df = _apply_search(df, search, search_columns, search_mode)

            if sort_model:
                by = [s["colId"] for s in sort_model if s.get("colId") in df.columns]
                desc = [s.get("sort") == "desc" for s in sort_model
                        if s.get("colId") in df.columns]
                if by:
                    df = df.sort(by=by, descending=desc, nulls_last=True)

            total = df.height
            page = df.slice(start, max(0, end - start))
            return {"rows": rows_to_records(page), "lastRow": total}

    # -- row operations ---------------------------------------------------
    def update_cell(self, row_id: int, field_name: str, value: Any) -> None:
        with self._lock:
            df = self.df
            if field_name not in df.columns or field_name == ID_COL:
                raise ValueError(f"Unknown column: {field_name}")
            self._snapshot(f"Edit {field_name}")
            dtype = df.schema[field_name]
            cast_val, df = _coerce_for_assign(df, field_name, dtype, value)
            mask = pl.col(ID_COL) == row_id
            self._df = df.with_columns(
                pl.when(mask).then(pl.lit(cast_val)).otherwise(pl.col(field_name)).alias(field_name)
            )

    def add_row(self) -> int:
        with self._lock:
            df = self.df
            self._snapshot("Add row")
            new_id = self._next_id
            row = {c: None for c in data_columns(df)}
            row[ID_COL] = new_id
            self._next_id += 1
            new = pl.DataFrame([row], schema=df.schema)
            self._df = pl.concat([df, new], how="vertical_relaxed")
            return new_id

    def delete_rows(self, ids: list[int]) -> int:
        with self._lock:
            df = self.df
            self._snapshot("Delete rows")
            before = df.height
            self._df = df.filter(~pl.col(ID_COL).is_in(ids))
            return before - self._df.height

    def duplicate_rows(self, ids: list[int]) -> int:
        with self._lock:
            df = self.df
            self._snapshot("Duplicate rows")
            dup = df.filter(pl.col(ID_COL).is_in(ids))
            if dup.height == 0:
                return 0
            new_ids = self._new_ids(dup.height)
            dup = dup.with_columns(new_ids)
            self._df = pl.concat([df, dup], how="vertical_relaxed")
            return dup.height


def _apply_search(
    df: pl.DataFrame, term: str, columns: list[str] | None, mode: str
) -> pl.DataFrame:
    cols = [c for c in (columns or data_columns(df)) if c in df.columns]
    if not cols:
        return df
    exprs = []
    for c in cols:
        s = pl.col(c).cast(pl.Utf8, strict=False)
        if mode == "exact":
            exprs.append(s == term)
        elif mode == "starts":
            exprs.append(s.str.starts_with(term))
        elif mode == "ends":
            exprs.append(s.str.ends_with(term))
        elif mode == "regex":
            exprs.append(s.str.contains(term))
        else:  # contains (case-insensitive)
            exprs.append(s.str.contains("(?i)" + _escape_regex(term)))
    combined = exprs[0]
    for e in exprs[1:]:
        combined = combined | e
    return df.filter(combined.fill_null(False))


def _escape_regex(text: str) -> str:
    import re
    return re.escape(text)


def _coerce_for_assign(
    df: pl.DataFrame, field_name: str, dtype: pl.DataType, value: Any
):
    """Try to keep the column dtype; if value won't fit, promote column to Utf8."""
    if value is None or value == "":
        return None, df
    try:
        if dtype in pl.NUMERIC_DTYPES:
            num = float(value)
            if dtype in pl.INTEGER_DTYPES and float(num).is_integer():
                return int(num), df
            return num, df
        if dtype == pl.Boolean:
            return str(value).strip().lower() in ("1", "true", "yes", "y"), df
    except (ValueError, TypeError):
        # Promote the whole column to string so the edit always succeeds.
        df = df.with_columns(pl.col(field_name).cast(pl.Utf8, strict=False))
        return str(value), df
    return value, df


# Single shared instance for this single-user application.
store = DataStore()
