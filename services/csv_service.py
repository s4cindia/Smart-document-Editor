"""CSV / TSV reading and writing on Polars (with robust fallbacks)."""
from __future__ import annotations

from pathlib import Path

import polars as pl


def read_csv(path: str | Path, separator: str | None = None) -> pl.DataFrame:
    """Read a CSV/TSV file. Separator is inferred from the extension if omitted.

    Every column is read as text (no type inference). This is deliberate: the
    app is a document editor, so values must be preserved exactly as written —
    e.g. a WCAG criterion like "1.4.3" must never be coerced into a date
    ("0003-04-01"), and IDs/codes must keep leading zeros and punctuation."""
    path = Path(path)
    if separator is None:
        separator = "\t" if path.suffix.lower() == ".tsv" else ","
    return pl.read_csv(
        path,
        separator=separator,
        infer_schema_length=0,    # treat every column as Utf8 text
        try_parse_dates=False,    # never turn "1.4.3" / "01-02" into a date
        has_header=True,
        truncate_ragged_lines=True,
        ignore_errors=True,
    )


def write_csv(df: pl.DataFrame, out_path: str | Path, separator: str = ",") -> Path:
    out_path = Path(out_path)
    df.write_csv(out_path, separator=separator)
    return out_path
