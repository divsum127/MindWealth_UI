"""Backfill shadow v2 regime log and emission vectors."""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd

from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.engine.regime_v2_shadow import build_regime_v2, twy_roc_at_date

logger = logging.getLogger("macro.regime_v2")


V2_TABLE_SQL = """
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


def ensure_v2_tables() -> None:
    init_db()
    with get_connection() as conn:
        conn.executescript(V2_TABLE_SQL)
        conn.commit()


def latest_regime_v2_date() -> str | None:
    """Most recent Friday already evaluated in macro_regime_log_v2."""
    ensure_v2_tables()
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(date) AS d FROM macro_regime_log_v2").fetchone()
    return row["d"] if row and row["d"] else None


def backfill_regime_v2(start: str = "1990-01-01", end: str | None = None) -> int:
    """Evaluate the v2 shadow regime for every Friday in [start, end] and upsert it.

    Errors are counted and logged rather than swallowed: this ran only from the manual
    experiment entrypoint, so a date that silently failed left a hole nobody saw. The table
    stopped at 2026-06-05 for that reason -- it had no scheduled caller at all until
    ``jobs/friday_pull`` started invoking ``update_regime_v2_to_date`` (2026-08-18).
    """
    ensure_v2_tables()
    end = end or pd.Timestamp.now().strftime("%Y-%m-%d")
    dates = pd.date_range(start, end, freq="W-FRI")
    n = 0
    failures: list[tuple[str, str]] = []
    with get_connection() as conn:
        for i, dt in enumerate(dates):
            ds = dt.strftime("%Y-%m-%d")
            try:
                reg = build_regime_v2(ds)
                reg["twy_roc"] = twy_roc_at_date(ds)
                conn.execute(
                    """
                    INSERT INTO macro_regime_log_v2 (date, regime_json, model)
                    VALUES (?, ?, 'v2_shadow')
                    ON CONFLICT(date) DO UPDATE SET regime_json=excluded.regime_json
                    """,
                    (ds, json.dumps(reg)),
                )
                n += 1
                if (i + 1) % 200 == 0:
                    conn.commit()
            except Exception as exc:
                failures.append((ds, f"{type(exc).__name__}: {exc}"))
                continue
        conn.commit()
    if failures:
        logger.warning(
            "regime_v2 backfill: %d of %d dates failed (first 5: %s)",
            len(failures),
            len(dates),
            failures[:5],
        )
    logger.info("regime_v2 backfill wrote %d of %d Fridays", n, len(dates))
    return n


def update_regime_v2_to_date(as_of: str | None = None, *, lookback_weeks: int = 8) -> int:
    """Bring macro_regime_log_v2 up to `as_of`, re-evaluating a short recent window.

    Called by the Friday job. The table is Friday-evaluated, so the Friday pull is its natural
    host. The small lookback re-evaluates the most recent Fridays because the macro inputs
    behind them (CAPE, NFCI, curve) get revised after first publication.
    """
    as_of = as_of or pd.Timestamp.now().strftime("%Y-%m-%d")
    latest = latest_regime_v2_date()
    if latest:
        start = (pd.Timestamp(latest) - pd.Timedelta(weeks=lookback_weeks)).strftime("%Y-%m-%d")
    else:
        start = "1990-01-01"
    return backfill_regime_v2(start, as_of)


def backfill_emission_vectors(start: str = "2010-01-01") -> int:
    ensure_v2_tables()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, var_id, unconditional_pctile, regime_pctile
            FROM daily_readings
            WHERE date >= ?
            ORDER BY date, var_id
            """,
            (start,),
        ).fetchall()
        n = 0
        for r in rows:
            un = r["unconditional_pctile"]
            rp = r["regime_pctile"]
            fallback = 1 if rp is None and un is not None else 0
            conn.execute(
                """
                INSERT INTO emission_vectors (date, var_id, unconditional_pctile, regime_pctile, fallback_used)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date, var_id) DO UPDATE SET
                  unconditional_pctile=excluded.unconditional_pctile,
                  regime_pctile=excluded.regime_pctile,
                  fallback_used=excluded.fallback_used
                """,
                (r["date"], r["var_id"], un, rp, fallback),
            )
            n += 1
        conn.commit()
    return n


def regime_label_distribution() -> dict[str, Any]:
    ensure_v2_tables()
    with get_connection() as conn:
        rows = conn.execute("SELECT regime_json FROM macro_regime_log_v2").fetchall()
    counts: dict[str, dict[str, int]] = {}
    for r in rows:
        reg = json.loads(r["regime_json"])
        for key in ("fed_cycle_v2", "curve_regime_v2", "liquidity_v2", "geo_overlay_v2", "val_regime"):
            val = str(reg.get(key, "UNKNOWN"))
            counts.setdefault(key, {})
            counts[key][val] = counts[key].get(val, 0) + 1
    return {"dimensions": counts, "n_dates": len(rows)}
