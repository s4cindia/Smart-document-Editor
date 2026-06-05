"""Filesystem helpers: safe names, extension checks, recent-file tracking."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from config import config

_RECENT_FILE = config.data_dir / "recent_files.json"
_MAX_RECENT = 15


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in config.allowed_extensions


def safe_filename(filename: str) -> str:
    """Strip path components and dangerous characters from an uploaded name."""
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name).strip()
    return name or f"upload_{int(time.time())}"


def unique_path(directory: Path, filename: str) -> Path:
    """Return a non-colliding path inside *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    base = Path(filename).stem
    ext = Path(filename).suffix
    candidate = directory / filename
    counter = 1
    while candidate.exists():
        candidate = directory / f"{base}_{counter}{ext}"
        counter += 1
    return candidate


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


# ---- Recent files ---------------------------------------------------------

def load_recent() -> list[dict]:
    if not _RECENT_FILE.exists():
        return []
    try:
        return json.loads(_RECENT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def add_recent(path: str | Path, sheet: str | None = None) -> None:
    path = str(path)
    recents = [r for r in load_recent() if r.get("path") != path]
    entry = {"path": path, "name": Path(path).name, "sheet": sheet, "ts": time.time()}
    recents.insert(0, entry)
    recents = recents[:_MAX_RECENT]
    try:
        _RECENT_FILE.write_text(json.dumps(recents, indent=2), encoding="utf-8")
    except OSError:
        pass


def list_folder(folder: str | Path) -> list[dict]:
    """List supported files in *folder* (non-recursive)."""
    p = Path(folder).expanduser()
    if not p.exists() or not p.is_dir():
        return []
    out = []
    for child in sorted(p.iterdir()):
        if child.is_file() and child.suffix.lower() in config.allowed_extensions:
            try:
                out.append({
                    "path": str(child),
                    "name": child.name,
                    "size": human_size(child.stat().st_size),
                    "ext": child.suffix.lower(),
                })
            except OSError:
                continue
    return out
