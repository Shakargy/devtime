"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from devtime import paths


def connect(root: Path | None = None) -> sqlite3.Connection:
    """Open the local memory database with sane defaults."""
    conn = sqlite3.connect(paths.db_path(root))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
