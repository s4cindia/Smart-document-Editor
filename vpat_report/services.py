"""VPAT / Delivery Outputs service facade."""
from __future__ import annotations

from services import feature_service


def report(path):
    """Generate the VPAT/delivery outputs. Returns (outputs, stats, preview)."""
    return feature_service.vpat_report(path)


def delivery_summary(df):
    """Summarise loaded delivery data by WCAG version / priority."""
    return feature_service.summarize_delivery(df)


def export_template(df, stem="delivery", title="", course="", details=""):
    """Export the loaded data via the delivery template. Returns (path, used)."""
    from services import feature_service
    return feature_service.export_via_template(df, stem=stem, title=title,
                                               course=course, details=details)
