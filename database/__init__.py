"""Database package for the Smart Document Editor.

Backend-agnostic (MySQL or SQLite) via SQLAlchemy. Exposes the engine helpers
(db.py) and the user data-access layer (models.py). Import `init_db()` at app
startup to ensure the schema exists.
"""
from database.db import get_engine, init_db, users  # noqa: F401
from database.models import (  # noqa: F401
    User,
    create_user,
    delete_user,
    get_user,
    list_users,
    update_role,
    user_count,
    verify_user,
)
