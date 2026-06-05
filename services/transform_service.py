"""Bulk editing / transform engine.

Every operation returns a new Polars DataFrame and a short description; the
caller (route) is responsible for committing it through the store so undo/redo
works uniformly. A ``preview`` helper shows the effect on a sample first.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import polars as pl

from utils.helpers import ID_COL, data_columns

Scope = str  # "all" | "selected"


def _target_columns(df: pl.DataFrame, columns: list[str] | None) -> list[str]:
    cols = columns or data_columns(df)
    return [c for c in cols if c in df.columns and c != ID_COL]


def _scoped_mask(df: pl.DataFrame, scope: Scope, ids: list[int] | None) -> pl.Expr:
    if scope == "selected" and ids:
        return pl.col(ID_COL).is_in(ids)
    return pl.lit(True)


def _apply_string_op(df: pl.DataFrame, columns: list[str], mask: pl.Expr,
                     fn: Callable[[pl.Expr], pl.Expr]) -> pl.DataFrame:
    exprs = []
    for c in columns:
        base = pl.col(c).cast(pl.Utf8, strict=False)
        new = fn(base)
        exprs.append(pl.when(mask).then(new).otherwise(pl.col(c)).alias(c))
    return df.with_columns(exprs)


# -- operations -------------------------------------------------------------

def replace_value(df, find, replace, columns=None, scope="all", ids=None,
                  literal=True):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    fn = lambda e: e.str.replace_all(find, replace, literal=literal)  # noqa: E731
    return _apply_string_op(df, cols, mask, fn), f"Replace '{find}' -> '{replace}'"


def regex_replace(df, pattern, replace, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    fn = lambda e: e.str.replace_all(pattern, replace, literal=False)  # noqa: E731
    return _apply_string_op(df, cols, mask, fn), f"Regex replace /{pattern}/"


def trim_spaces(df, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    fn = lambda e: e.str.strip_chars()  # noqa: E731
    return _apply_string_op(df, cols, mask, fn), "Trim spaces"


def to_upper(df, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    return _apply_string_op(df, cols, mask, lambda e: e.str.to_uppercase()), "Upper case"


def to_lower(df, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    return _apply_string_op(df, cols, mask, lambda e: e.str.to_lowercase()), "Lower case"


def to_proper(df, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    fn = lambda e: e.str.to_titlecase()  # noqa: E731
    return _apply_string_op(df, cols, mask, fn), "Proper case"


def append_text(df, text, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    fn = lambda e: e.fill_null("") + pl.lit(text)  # noqa: E731
    return _apply_string_op(df, cols, mask, fn), f"Append '{text}'"


def prepend_text(df, text, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    fn = lambda e: pl.lit(text) + e.fill_null("")  # noqa: E731
    return _apply_string_op(df, cols, mask, fn), f"Prepend '{text}'"


def remove_special(df, columns=None, scope="all", ids=None, keep_spaces=True):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    pattern = r"[^A-Za-z0-9 ]" if keep_spaces else r"[^A-Za-z0-9]"
    fn = lambda e: e.str.replace_all(pattern, "")  # noqa: E731
    return _apply_string_op(df, cols, mask, fn), "Remove special characters"


def null_replace(df, replacement, columns=None, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    exprs = []
    for c in cols:
        base = pl.col(c).cast(pl.Utf8, strict=False)
        filled = base.fill_null(replacement)
        exprs.append(pl.when(mask).then(filled).otherwise(pl.col(c)).alias(c))
    return df.with_columns(exprs), f"Replace nulls with '{replacement}'"


def merge_columns(df, columns, target, separator=" "):
    cols = [c for c in columns if c in df.columns]
    if len(cols) < 2:
        raise ValueError("Select at least two columns to merge.")
    expr = pl.concat_str([pl.col(c).cast(pl.Utf8, strict=False).fill_null("")
                          for c in cols], separator=separator).alias(target)
    return df.with_columns(expr), f"Merge {cols} -> {target}"


def split_column(df, column, separator, into=None):
    if column not in df.columns:
        raise ValueError(f"Unknown column: {column}")
    sample = df.with_columns(
        pl.col(column).cast(pl.Utf8, strict=False)
        .str.split(separator).alias("__parts")
    )
    max_parts = int(sample.select(pl.col("__parts").list.len().max()).item() or 1)
    names = into or [f"{column}_{i+1}" for i in range(max_parts)]
    names = names[:max_parts]
    exprs = [
        sample.get_column("__parts").list.get(i, null_on_oob=True).alias(names[i])
        for i in range(len(names))
    ]
    new = sample.drop("__parts").with_columns(exprs)
    return new, f"Split {column} by '{separator}'"


def format_numbers(df, columns, decimals=2, scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    exprs = []
    for c in cols:
        num = pl.col(c).cast(pl.Float64, strict=False).round(decimals)
        exprs.append(pl.when(mask).then(num).otherwise(pl.col(c)).alias(c))
    return df.with_columns(exprs), f"Format numbers ({decimals} dp)"


def format_dates(df, columns, fmt="%Y-%m-%d", scope="all", ids=None):
    cols = _target_columns(df, columns)
    mask = _scoped_mask(df, scope, ids)
    exprs = []
    for c in cols:
        parsed = (pl.col(c).cast(pl.Utf8, strict=False)
                  .str.to_datetime(strict=False, exact=False))
        formatted = parsed.dt.strftime(fmt)
        exprs.append(pl.when(mask).then(formatted).otherwise(pl.col(c)).alias(c))
    return df.with_columns(exprs), f"Format dates ({fmt})"


def preview(df: pl.DataFrame, op_result_df: pl.DataFrame, columns: list[str] | None,
            sample: int = 8) -> dict[str, Any]:
    """Build a before/after preview for the affected columns."""
    cols = _target_columns(df, columns)
    before = df.select([ID_COL, *cols]).head(sample)
    after_cols = [c for c in cols if c in op_result_df.columns]
    after = op_result_df.select([ID_COL, *after_cols]).head(sample)
    from utils.helpers import rows_to_records
    return {
        "columns": cols,
        "before": rows_to_records(before),
        "after": rows_to_records(after),
    }
