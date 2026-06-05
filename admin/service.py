"""Admin service facade over the SQLite user layer."""
from __future__ import annotations

from database import models


def all_users():
    return models.list_users()


def add_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
    return models.create_user(username, password, role)


def remove_user(user_id: int) -> tuple[bool, str]:
    return models.delete_user(user_id)
