"""CSV / TSV reading and writing on Polars (with robust fallbacks)."""
from __future__ import annotations

from pathlib import Path

import polars as pl


def read_csv(path: str | Path, separator: str | None = None) -> pl.DataFrame:
    """Read a CSV/TSV file. Separator is inferred from the extension if omitted."""
    path = Path(path)
    if separator is None:
        separator = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        return pl.read_csv(
            path,
            separator=separator,
            infer_schema_length=10000,
            try_parse_dates=True,
            ignore_errors=True,
            truncate_ragged_lines=True,
        )
    except Exception:  # noqa: BLE001 - last-resort, read everything as text
        return pl.read_csv(
            path,
            separator=separator,
            infer_schema_length=0,
            has_header=True,
            truncate_ragged_lines=True,
            ignore_errors=True,
        )


def write_csv(df: pl.DataFrame, out_path: str | Path, separator: str = ",") -> Path:
    out_path = Path(out_path)
    df.write_csv(out_path, separator=separator)
    return out_path
