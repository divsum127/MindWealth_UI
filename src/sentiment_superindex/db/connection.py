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


def _legacy_input_raw(payload: dict[str, Any], key: str) -> float | None:
    """Extract legacy four-input raw values from current or historical payload shape."""
    inputs = payload.get("inputs") or {}
    layer2 = inputs.get("layer2") or {}
    layer3 = inputs.get("layer3") or {}
    layer1 = inputs.get("layer1") or {}
    components = {
        "hyg_lqd": inputs.get("layer2_components", {}).get("hyg_lqd", {}),
        "dbmf_beta": inputs.get("layer3_components", {}).get("dbmf_beta", {}),
        "cnn_fg": inputs.get("layer1_components", {}).get("cnn_fg", {}),
        "vix_ratio": inputs.get("layer2_components", {}).get("vix_ratio", {}),
    }
    legacy = inputs.get(key, {})
    if isinstance(legacy, dict) and legacy.get("raw") is not None:
        return legacy.get("raw")
    comp = components.get(key, {})
    if isinstance(comp, dict) and comp.get("raw") is not None:
        return comp.get("raw")
    flat_map = {
        "hyg_lqd": layer2.get("hyg_lqd"),
        "dbmf_beta": layer3.get("dbmf_beta"),
        "cnn_fg": layer1.get("cnn_fg_raw"),
        "vix_ratio": layer2.get("vix_ratio"),
    }
    val = flat_map.get(key)
    return float(val) if val is not None else None


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
                _legacy_input_raw(payload, "hyg_lqd"),
                _legacy_input_raw(payload, "dbmf_beta"),
                _legacy_input_raw(payload, "cnn_fg"),
                _legacy_input_raw(payload, "vix_ratio"),
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
