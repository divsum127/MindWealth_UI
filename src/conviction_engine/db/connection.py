"""SQLite connection for conviction auxiliary tables."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from ...config_paths import CONVICTION_STORE_DIR

DEFAULT_DB = CONVICTION_STORE_DIR.parent / "conviction_aux.db"
_SCHEMA = Path(__file__).with_name("schema.sql")


def _ensure_schema(conn: sqlite3.Connection) -> None:
    if _SCHEMA.exists():
        conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


@contextmanager
def get_connection(path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    db = path or DEFAULT_DB
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        yield conn
    finally:
        conn.close()


def execute(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    return conn.execute(sql, params)
