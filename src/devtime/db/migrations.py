"""Database initialization and migrations (Builder Edition, Chapter 20).

Every release can change what users believe, so migrations must preserve
decisions, challenged claims, rejected claims, and human confirmations.
V0 ships a single schema version; the migration framework is in place so later
versions can back up and migrate without losing memory.
"""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from devtime import __version__, config, paths
from devtime.db import connection

SCHEMA_VERSION = 1
SCHEMA_FILE = Path(__file__).with_name("schema.sql")
IGNORE_STARTER = (
    Path(__file__).resolve().parents[1] / "assets" / "devtimeignore.starter"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs(root: Path | None = None) -> None:
    paths.devtime_dir(root).mkdir(parents=True, exist_ok=True)
    paths.backups_dir(root).mkdir(parents=True, exist_ok=True)
    paths.logs_dir(root).mkdir(parents=True, exist_ok=True)


def _write_starter_files(root: Path | None = None) -> None:
    cfg = paths.config_path(root)
    if not cfg.exists():
        cfg.write_text(config.default_config_yaml(), encoding="utf-8")
    ignore = paths.ignore_path(root)
    if not ignore.exists() and IGNORE_STARTER.exists():
        ignore.write_text(IGNORE_STARTER.read_text(encoding="utf-8"), encoding="utf-8")


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if row is None:
        return 0
    res = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return int(res["v"]) if res and res["v"] is not None else 0


def _apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


def init_repo(root: Path | None = None) -> str:
    """Create local DevTime memory safely. Returns the repository id."""
    _ensure_dirs(root)
    _write_starter_files(root)

    conn = connection.connect(root)
    try:
        _apply_schema(conn)
        version = current_version(conn)
        if version < SCHEMA_VERSION:
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, _now()),
            )

        root_path = str((root or paths.repo_root()).resolve())
        existing = conn.execute("SELECT id FROM repositories LIMIT 1").fetchone()
        if existing:
            repo_id = existing["id"]
            conn.execute(
                "UPDATE repositories SET root_path = ?, updated_at = ? WHERE id = ?",
                (root_path, _now(), repo_id),
            )
        else:
            repo_id = f"repo-{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO repositories(id, root_path, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (repo_id, root_path, _now(), _now()),
            )
        conn.commit()
        return repo_id
    finally:
        conn.close()


def backup_database(from_version: int, root: Path | None = None) -> Path | None:
    """Create a pre-migration backup (Chapter 20 migration flow step 2)."""
    db = paths.db_path(root)
    if not db.exists():
        return None
    dest = paths.backups_dir(root) / f"devtime-before-schema-{from_version}.sqlite"
    shutil.copy2(db, dest)
    return dest


def get_repository_id(root: Path | None = None) -> str | None:
    if not paths.is_initialized(root):
        return None
    conn = connection.connect(root)
    try:
        row = conn.execute("SELECT id FROM repositories LIMIT 1").fetchone()
        return row["id"] if row else None
    finally:
        conn.close()
