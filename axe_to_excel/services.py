"""Generate Axe 2 Excel service facade."""
from __future__ import annotations

from services import feature_service


def convert(path, sheet=None, parent_id="", out_name=""):
    """Convert an axe workbook to the audit format.

    Returns (outputs, stats, preview).
    """
    return feature_service.axe_to_audit(
        path, sheet=sheet, parent_id=parent_id, out_name=out_name)


def sheets_for(path):
    """Worksheet names for the sheet picker."""
    return feature_service.list_sheets_for(path)
