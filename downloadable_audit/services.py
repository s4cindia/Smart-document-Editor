"""Generate Excel for Downloadable service facade."""
from __future__ import annotations

from services import feature_service


def generate(path, parent_id="", sheet=None):
    """Build the downloadable-documents workbook.

    Returns (outputs, stats, preview).
    """
    return feature_service.downloadable_docs(path, parent_id=parent_id, sheet=sheet)
