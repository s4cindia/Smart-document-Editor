"""User data-access layer (the only table is `users`).

Backend-agnostic (MySQL or SQLite) via SQLAlchemy. Self-registration is
intentionally NOT supported anywhere in the app; users are provisioned by an
administrator via create_user.py, which calls `create_user()` here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_engine, init_db, users

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,32}$")
_VALID_ROLES = {"user", "admin"}


@dataclass
class User:
    id: int
    username: str
    role: str
    created_at: str


def _to_user(row) -> User:
    m = row._mapping
    return User(id=m["id"], username=m["username"],
                role=m["role"], created_at=str(m["created_at"]))


def user_count(db_path: str | Path | None = None) -> int:
    eng = get_engine(db_path)
    with eng.connect() as c:
        return int(c.execute(select(func.count()).select_from(users)).scalar() or 0)


def get_user(username: str, db_path: str | Path | None = None) -> User | None:
    eng = get_engine(db_path)
    uname = (username or "").strip()
    with eng.connect() as c:
        row = c.execute(
            select(users).where(func.lower(users.c.username) == uname.lower())
        ).first()
    return _to_user(row) if row else None


def list_users(db_path: str | Path | None = None) -> list[User]:
    eng = get_engine(db_path)
    with eng.connect() as c:
        rows = c.execute(select(users).order_by(func.lower(users.c.username))).all()
    return [_to_user(r) for r in rows]


def create_user(username: str, password: str, role: str = "user",
                db_path: str | Path | None = None) -> tuple[bool, str]:
    """Validate and insert a new user. Returns (ok, message)."""
    username = (username or "").strip()
    role = (role or "user").strip().lower()
    if not _USERNAME_RE.match(username):
        return False, ("Username must be 3-32 characters: letters, numbers, "
                       "dot, dash or underscore.")
    if len(password or "") < 6:
        return False, "Password must be at least 6 characters."
    if role not in _VALID_ROLES:
        return False, f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}."

    init_db(db_path)
    if get_user(username, db_path) is not None:
        return False, "That username already exists."
    eng = get_engine(db_path)
    try:
        with eng.begin() as c:
            c.execute(insert(users).values(
                username=username,
                password_hash=generate_password_hash(password),
                role=role))
    except IntegrityError:
        return False, "That username already exists."
    return True, f"User '{username}' created with role '{role}'."


def verify_user(username: str, password: str,
                db_path: str | Path | None = None) -> tuple[bool, str]:
    """Validate login credentials. Returns (ok, display_name_or_error)."""
    eng = get_engine(db_path)
    uname = (username or "").strip()
    with eng.connect() as c:
        row = c.execute(
            select(users).where(func.lower(users.c.username) == uname.lower())
        ).first()
    if not row or not check_password_hash(row._mapping["password_hash"], password or ""):
        return False, "Invalid username or password."
    return True, row._mapping["username"]


def update_role(username: str, role: str,
                db_path: str | Path | None = None) -> tuple[bool, str]:
    """Change an existing user's role. Returns (ok, message)."""
    role = (role or "").strip().lower()
    if role not in _VALID_ROLES:
        return False, f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}."
    eng = get_engine(db_path)
    with eng.begin() as c:
        row = c.execute(
            select(users).where(func.lower(users.c.username) == (username or "").strip().lower())
        ).first()
        if not row:
            return False, f"No such user: {username}"
        m = row._mapping
        if m["role"] == "admin" and role != "admin":
            admins = c.execute(
                select(func.count()).select_from(users).where(users.c.role == "admin")
            ).scalar()
            if (admins or 0) <= 1:
                return False, "Cannot demote the only administrator."
        c.execute(update(users).where(users.c.id == m["id"]).values(role=role))
    return True, f"User '{m['username']}' is now '{role}'."


def delete_user(user_id: int, db_path: str | Path | None = None) -> tuple[bool, str]:
    """Delete a user by id. Refuses to remove the last remaining admin."""
    eng = get_engine(db_path)
    with eng.begin() as c:
        row = c.execute(select(users).where(users.c.id == user_id)).first()
        if not row:
            return False, "User not found."
        m = row._mapping
        if m["role"] == "admin":
            admins = c.execute(
                select(func.count()).select_from(users).where(users.c.role == "admin")
            ).scalar()
            if (admins or 0) <= 1:
                return False, "Cannot delete the only administrator account."
        c.execute(delete(users).where(users.c.id == user_id))
    return True, f"User '{m['username']}' deleted."
