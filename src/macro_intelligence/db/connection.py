"""SQLite connection and schema initialization."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterator

from src.config_paths import MACRO_INTEL_DATA_DIR
from src.macro_intelligence.config import db_path, load_config

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def ensure_db_dir() -> None:
    MACRO_INTEL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def init_db(path: Path | None = None) -> Path:
    ensure_db_dir()
    db = path or db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed_variables(conn)
        conn.commit()
    finally:
        conn.close()
    return db


def _seed_variables(conn: sqlite3.Connection) -> None:
    cfg = load_config()
    for var in cfg.get("variables", []):
        ticker = var.get("ticker") or var.get("ticker_ratio")
        if isinstance(ticker, list):
            ticker = "/".join(str(t) for t in ticker)
        conn.execute(
            """
            INSERT OR IGNORE INTO variables
            (var_id, name, source_ticker, paradigm, combo_slots, pctile_window, pctile_start)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                var["id"],
                var["name"],
                ticker,
                var.get("paradigm"),
                ",".join(str(c) for c in var.get("combos", [])),
                var.get("pctile_window", "rolling_3y"),
                var.get("pctile_start"),
            ),
        )


@contextmanager
def get_connection(path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    ensure_db_dir()
    db = path or db_path()
    if not db.exists():
        init_db(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    return conn.execute(sql, params)


def fetchall(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params).fetchall())


def fetchone(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    row = conn.execute(sql, params).fetchone()
    return row
