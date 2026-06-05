"""Validation + duplicate-detection facade for the Smart Editor."""
from __future__ import annotations

from services.duplicate_service import (  # noqa: F401
    drop_duplicates,
    find_duplicates,
)
from services.validation_service import error_rows, validate  # noqa: F401
