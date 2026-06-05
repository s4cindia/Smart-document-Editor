"""Authentication service.

Thin facade over the SQLite-backed user data-access layer
(``database.models``). Keeps the route handlers free of data-access details
and provides a single place to add auth-related logging.
"""
from __future__ import annotations

import logging

from database import models

log = logging.getLogger("sde.auth")


def verify_credentials(username: str, password: str) -> tuple[bool, str]:
    """Validate a login attempt.

    Returns ``(ok, display_name)`` on success, or ``(False, error_message)``.
    """
    ok, result = models.verify_user(username, password)
    if ok:
        log.info("Login success: %s", result)
    else:
        log.warning("Login failed for username=%r", (username or "").strip())
    return ok, result


def provision_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
    """Create a user (used by the admin CLI). Returns ``(ok, message)``."""
    return models.create_user(username, password, role)
