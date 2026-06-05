"""Application configuration for the Smart Document Editor & Validator.

Single-user / small-team local application. Authentication is backed by a
local SQLite database (login only; users are provisioned by an administrator
via create_user.py). Settings can be overridden with environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name)
    return Path(val).expanduser().resolve() if val else default


@dataclass
class Config:
    """Central configuration object.

    Paths are created on import so the app is runnable immediately.
    Environment overrides: SDE_SECRET_KEY, SDE_DB_PATH, SDE_DATA_DIR.
    """

    base_dir: Path = BASE_DIR
    upload_dir: Path = BASE_DIR / "uploads"
    export_dir: Path = BASE_DIR / "exports"
    report_dir: Path = BASE_DIR / "reports"
    data_dir: Path = field(default_factory=lambda: _env_path("SDE_DATA_DIR", BASE_DIR / "data"))

    # --- Database -----------------------------------------------------------
    # SQLite database file (used when the backend is sqlite).
    db_path: Path = field(default_factory=lambda: _env_path("SDE_DB_PATH", BASE_DIR / "database" / "users.db"))
    # Backend selector: "mysql" or "sqlite" (default). Override via SDE_DB_BACKEND.
    db_backend: str = field(default_factory=lambda: os.environ.get("SDE_DB_BACKEND", "sqlite").strip().lower())

    # Largest number of rows we ever push to the browser in one page.
    page_size_default: int = 100
    page_size_max: int = 1000

    # Undo/redo history depth (snapshots kept in memory).
    history_depth: int = 25

    # Accepted upload extensions.
    allowed_extensions: tuple[str, ...] = (
        ".xlsx", ".xls", ".csv", ".tsv", ".pdf",
    )

    # Max upload size (bytes). 200 MB is plenty for a local tool.
    max_content_length: int = 200 * 1024 * 1024

    # Session signing key. Override in production via SDE_SECRET_KEY.
    secret_key: str = field(
        default_factory=lambda: os.environ.get("SDE_SECRET_KEY", "smart-doc-editor-local-only"))

    def ensure_dirs(self) -> None:
        for d in (self.upload_dir, self.export_dir, self.report_dir, self.data_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def database_url(self) -> str:
        """SQLAlchemy connection URL.

        Priority:
          1. SDE_DB_URL  (full URL, e.g. mysql+pymysql://user:pw@host:3306/db)
          2. SDE_DB_BACKEND=mysql  → built from SDE_MYSQL_* env vars
          3. SQLite file at db_path (default; runs out of the box)
        """
        url = os.environ.get("SDE_DB_URL")
        if url:
            return url
        if self.db_backend == "mysql":
            from urllib.parse import quote_plus
            user = os.environ.get("SDE_MYSQL_USER", "root")
            pw = quote_plus(os.environ.get("SDE_MYSQL_PASSWORD", ""))
            host = os.environ.get("SDE_MYSQL_HOST", "127.0.0.1")
            port = os.environ.get("SDE_MYSQL_PORT", "3306")
            name = os.environ.get("SDE_MYSQL_DB", "smart_document_editor")
            return f"mysql+pymysql://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4"
        return f"sqlite:///{self.db_path}"


config = Config()
config.ensure_dirs()
