"""Excel read/write facade for the Smart Editor.

Re-exports the shared Excel service so the editor depends on a module-local
name rather than reaching across packages. The Summary-cell highlight on
export (length > 215 or contains a newline) lives in the shared service.
"""
from __future__ import annotations

from services.excel_service import (  # noqa: F401
    list_sheets,
    read_sheet,
    write_excel,
    write_excel_highlighted,
)
