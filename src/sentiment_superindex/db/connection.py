"""SQLite for SSI history."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from src.config_paths import SSI_DATA_DIR
from src.sentiment_superindex.config import db_path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(path: Path | None = None) -> Path:
    SSI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = path or db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return db


@contextmanager
def get_connection(path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    SSI_DATA_DIR.mkdir(parents=True, exist_ok=True)
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


def persist_daily(payload: dict[str, Any]) -> None:
    import json

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ssi_daily (
                date, ssi_level, ssi_percentile_5y, hyg_lqd, dbmf_beta, cnn_fg, vix_ratio,
                layer2_status, layer2_confirmed_count, ssi_multiplier, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                ssi_level=excluded.ssi_level,
                ssi_percentile_5y=excluded.ssi_percentile_5y,
                hyg_lqd=excluded.hyg_lqd,
                dbmf_beta=excluded.dbmf_beta,
                cnn_fg=excluded.cnn_fg,
                vix_ratio=excluded.vix_ratio,
                layer2_status=excluded.layer2_status,
                layer2_confirmed_count=excluded.layer2_confirmed_count,
                ssi_multiplier=excluded.ssi_multiplier,
                payload_json=excluded.payload_json
            """,
            (
                payload["date"],
                payload.get("ssi_level"),
                payload.get("ssi_percentile_5y"),
                payload.get("inputs", {}).get("hyg_lqd", {}).get("raw"),
                payload.get("inputs", {}).get("dbmf_beta", {}).get("raw"),
                payload.get("inputs", {}).get("cnn_fg", {}).get("raw"),
                payload.get("inputs", {}).get("vix_ratio", {}).get("raw"),
                payload.get("layer2_status"),
                payload.get("layer2_confirmed_count"),
                payload.get("ssi_multiplier"),
                json.dumps(payload),
            ),
        )


def load_history_levels() -> list[tuple[str, float]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, ssi_level FROM ssi_daily ORDER BY date"
        ).fetchall()
    return [(r["date"], float(r["ssi_level"])) for r in rows]
