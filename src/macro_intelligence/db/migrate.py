"""Apply schema migrations for existing runic.db instances."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS = [
    "ALTER TABLE daily_readings ADD COLUMN unconditional_pctile REAL",
    "ALTER TABLE daily_readings ADD COLUMN regime_pctile REAL",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_regime_log_date ON macro_regime_log(date)",
    "ALTER TABLE forward_returns ADD COLUMN spx_9m REAL",
    "ALTER TABLE forward_returns ADD COLUMN spx_12m REAL",
    "ALTER TABLE combo_c_cancel ADD COLUMN cancel_date TEXT",
]

_V2_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS macro_regime_log_v2 (
    date TEXT PRIMARY KEY,
    regime_json TEXT NOT NULL,
    model TEXT DEFAULT 'v2_shadow',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS emission_vectors (
    date TEXT NOT NULL,
    var_id TEXT NOT NULL,
    unconditional_pctile REAL,
    regime_pctile REAL,
    fallback_used INTEGER DEFAULT 0,
    PRIMARY KEY (date, var_id)
);
CREATE INDEX IF NOT EXISTS idx_emission_vectors_date ON emission_vectors(date);
"""


def migrate_db(path: Path | None = None) -> None:
    from src.macro_intelligence.db.connection import init_db, db_path

    db = path or db_path()
    if not db.exists():
        init_db(db)
        return
    conn = sqlite3.connect(db)
    try:
        conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
        for sql in _MIGRATIONS:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        conn.execute(
            "INSERT OR IGNORE INTO combo_c_cancel (id, wti_potential_week) VALUES (1, 0)"
        )
        try:
            conn.execute(
                """
                DELETE FROM macro_regime_log
                WHERE log_id NOT IN (
                    SELECT MAX(log_id) FROM macro_regime_log GROUP BY date
                )
                """
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.executescript(_V2_TABLES_SQL)
        except sqlite3.OperationalError:
            pass
        conn.commit()
    finally:
        conn.close()
