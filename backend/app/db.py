"""SQLite connection and migration runner."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import BACKEND_DIR, PROJECT_ROOT


DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"
DB_PATH = Path(os.environ.get("APP_DB_PATH", str(DEFAULT_DB_PATH)))
MIGRATIONS_DIR = BACKEND_DIR / "migrations"

_lock = threading.Lock()

_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT    NOT NULL,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    checksum    TEXT    NOT NULL
);
"""


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_parent(DB_PATH)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def cursor():
    conn = get_connection()
    try:
        with _lock:
            cur = conn.cursor()
            yield cur
            conn.commit()
    finally:
        conn.close()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _pending_migrations(applied: dict[str, str]) -> list[tuple[str, str, Path]]:
    """Return unapplied (version, name, path) sorted by version."""
    pattern = re.compile(r"^V(\d+)__(.+)\.sql$")
    pending = []
    for path in sorted(MIGRATIONS_DIR.glob("V*.sql")):
        m = pattern.match(path.name)
        if not m:
            continue
        version, name = m.group(1), m.group(2)
        sql = path.read_text(encoding="utf-8")
        checksum = _sha256(sql)
        if version in applied:
            if applied[version] != checksum:
                raise RuntimeError(
                    f"Migration V{version}__{name}.sql was modified after it was applied. "
                    "Never edit an applied migration — add a new one instead."
                )
            continue
        pending.append((version, name, path))
    return pending


def migrate() -> None:
    """Apply all pending migrations. Safe to call on every startup."""
    conn = get_connection()
    try:
        with _lock:
            conn.executescript(_BOOTSTRAP)

            applied = {
                row["version"]: row["checksum"]
                for row in conn.execute("SELECT version, checksum FROM schema_migrations")
            }

            for version, name, path in _pending_migrations(applied):
                sql = path.read_text(encoding="utf-8")
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (?, ?, ?)",
                    (version, name, _sha256(sql)),
                )
                conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    migrate()
