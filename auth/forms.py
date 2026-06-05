"""Lightweight login input validation.

A dependency-free stand-in for a forms library: validates the raw login
fields before they reach the service layer.
"""
from __future__ import annotations


def validate_login(username: str, password: str) -> tuple[bool, str]:
    """Return ``(ok, error_message)`` for the submitted login fields."""
    if not (username or "").strip():
        return False, "Please enter your username."
    if not (password or ""):
        return False, "Please enter your password."
    return True, ""
