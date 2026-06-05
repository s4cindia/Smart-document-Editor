"""Smart Editor service facade.

Exposes the data-store, transform dispatch table, analytics and export
operations the editor routes need, so the routes stay thin.
"""
from __future__ import annotations

from services import analytics_service, export_service, transform_service
from services.store import store  # noqa: F401

# Transform dispatch table: op name -> callable(df, params) -> (new_df, desc)
TRANSFORMS = {
    "replace": lambda df, p: transform_service.replace_value(
        df, p.get("find", ""), p.get("replace", ""), p.get("columns"),
        p.get("scope", "all"), p.get("ids")),
    "regex_replace": lambda df, p: transform_service.regex_replace(
        df, p.get("pattern", ""), p.get("replace", ""), p.get("columns"),
        p.get("scope", "all"), p.get("ids")),
    "trim": lambda df, p: transform_service.trim_spaces(
        df, p.get("columns"), p.get("scope", "all"), p.get("ids")),
    "upper": lambda df, p: transform_service.to_upper(
        df, p.get("columns"), p.get("scope", "all"), p.get("ids")),
    "lower": lambda df, p: transform_service.to_lower(
        df, p.get("columns"), p.get("scope", "all"), p.get("ids")),
    "proper": lambda df, p: transform_service.to_proper(
        df, p.get("columns"), p.get("scope", "all"), p.get("ids")),
    "append": lambda df, p: transform_service.append_text(
        df, p.get("text", ""), p.get("columns"), p.get("scope", "all"), p.get("ids")),
    "prepend": lambda df, p: transform_service.prepend_text(
        df, p.get("text", ""), p.get("columns"), p.get("scope", "all"), p.get("ids")),
    "remove_special": lambda df, p: transform_service.remove_special(
        df, p.get("columns"), p.get("scope", "all"), p.get("ids"),
        p.get("keep_spaces", True)),
    "null_replace": lambda df, p: transform_service.null_replace(
        df, p.get("replacement", ""), p.get("columns"), p.get("scope", "all"),
        p.get("ids")),
    "merge": lambda df, p: transform_service.merge_columns(
        df, p.get("columns", []), p.get("target", "merged"), p.get("separator", " ")),
    "split": lambda df, p: transform_service.split_column(
        df, p.get("column", ""), p.get("separator", ","), p.get("into")),
    "format_numbers": lambda df, p: transform_service.format_numbers(
        df, p.get("columns", []), int(p.get("decimals", 2)),
        p.get("scope", "all"), p.get("ids")),
    "format_dates": lambda df, p: transform_service.format_dates(
        df, p.get("columns", []), p.get("format", "%Y-%m-%d"),
        p.get("scope", "all"), p.get("ids")),
}


def transform_preview(df, new_df, columns):
    return transform_service.preview(df, new_df, columns)


def export(df, fmt: str, stem: str, highlight: bool = True):
    """Dispatch an export to the shared export service."""
    if fmt == "excel":
        return export_service.export_excel(df, stem, highlight=highlight)
    if fmt == "csv":
        return export_service.export_csv(df, stem)
    if fmt == "json":
        return export_service.export_json(df, stem)
    if fmt == "pdf":
        return export_service.export_pdf(df, stem)
    raise ValueError(f"Unsupported export format: {fmt}")


def report(df, kind: str, fmt: str):
    return export_service.generate_report(df, kind, fmt)


def analytics():
    return analytics_service
