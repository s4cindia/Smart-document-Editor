"""Database engine + schema (SQLAlchemy).

Backend-agnostic: the same code runs on MySQL or SQLite, selected by
``config.database_url()``. The only table is ``users``.

To use MySQL, set environment variables before launching the app, e.g.:
    SDE_DB_BACKEND=mysql
    SDE_MYSQL_HOST=127.0.0.1
    SDE_MYSQL_PORT=3306
    SDE_MYSQL_USER=vpat
    SDE_MYSQL_PASSWORD=secret
    SDE_MYSQL_DB=smart_document_editor
(or set a full SDE_DB_URL). Otherwise it falls back to a local SQLite file.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import (Column, DateTime, Integer, MetaData, String, Table,
                        create_engine, func)
from sqlalchemy.engine import Engine

from config import config

log = logging.getLogger("sde.database")

metadata = MetaData()

# Single source of truth for the users schema (portable across MySQL/SQLite).
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(64), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("role", String(16), nullable=False, server_default="user"),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)

_engine: Engine | None = None


def _make_engine(url: str) -> Engine:
    kwargs = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        # Allow use across Flask's threads for the local SQLite case.
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def get_engine(db_path: str | Path | None = None) -> Engine:
    """Return the shared engine, or a one-off SQLite engine for ``db_path``.

    ``db_path`` exists for backwards compatibility (tests / CLI that target a
    specific SQLite file). When omitted, the configured backend is used.
    """
    if db_path:
        return _make_engine(f"sqlite:///{Path(db_path)}")
    global _engine
    if _engine is None:
        url = config.database_url()
        _engine = _make_engine(url)
        log.info("Database engine: %s", url.split("://", 1)[0])
    return _engine


def init_db(db_path: str | Path | None = None) -> None:
    """Create the schema if it does not exist."""
    engine = get_engine(db_path)
    metadata.create_all(engine)
    log.info("Database ready (%s)", engine.url.get_backend_name())
