"""Merge Axe service facade."""
from __future__ import annotations

from services import feature_service


def merge(paths):
    """Merge axe workbooks. Returns (outputs, stats, preview)."""
    return feature_service.merge_axe(paths)
