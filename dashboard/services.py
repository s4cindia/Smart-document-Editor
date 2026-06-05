"""Dashboard services — metadata for the four feature cards.

The dashboard template currently renders the cards directly; this list is the
single source of truth other code can import (e.g. for tests or future
server-side rendering) so the card definitions are not duplicated.
"""
from __future__ import annotations

CARDS = [
    {
        "title": "Validate /Merge Axe Tool Excels",
        "href": "/merge-axe-excels",
        "icon": "fa-shuffle",
        "accent": "#2563eb",
        "description": "Combine multiple axe DevTools export workbooks into one.",
    },
    {
        "title": "Generate Axe 2 Excel",
        "href": "/generate-axe2-excel",
        "icon": "fa-chart-bar",
        "accent": "#0d9488",
        "description": "Convert axe output into the S4Carlisle audit format.",
    },
    {
        "title": "Validate / Generate Delivery Outputs",
        "href": "/vpat-generate-report",
        "icon": "fa-box",
        "accent": "#d97706",
        "description": "Validate a WCAG workbook and export delivery files.",
    },
    {
        "title": "Generate Excel for Downloadable",
        "href": "/generate-downloadable-excel",
        "icon": "fa-clipboard",
        "accent": "#7c3aed",
        "description": "List PDF / Word / PowerPoint documents from a media inventory.",
    },
]
