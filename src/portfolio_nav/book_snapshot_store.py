"""Daily book-state snapshot store — "set up books from today" infrastructure.

Where conviction overlay history (conviction_store/daily/) only starts 2026-05-15, and no
eviction/slot-occupancy or regime-bucket history exists in production at all, this store
starts capturing exact per-position book state every trading day from the day the daily job
(scripts/run_portfolio_book_snapshot_daily.py) first runs. It makes:

  - D1 sleeve/slot occupancy auditable going forward (which slot a position held, on what day)
  - four_book_engine NAV replay exact and reproducible from "today" forward, without re-deriving
  - the regime-bucket daily series Ahil's A1 four-book re-run reports against

No backfill is attempted for dates before first-run — see ``earliest_snapshot_date()``. Downstream
consumers must disclose that boundary via a ``data_status`` field, never fabricate it.

Schema is intentionally additive: new columns can be added (e.g. slot_index once the eviction
engine ships) without invalidating earlier rows, which simply carry NULL for that column.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator

from src.config_paths import BOOK_SNAPSHOTS_DB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS position_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    function        TEXT,
    interval        TEXT,
    direction       TEXT,
    sleeve_id       TEXT,
    sleeve_label    TEXT,
    conviction_tier TEXT,
    conviction_multiplier REAL,
    ssi_ceiling_scalar REAL,
    regime_bucket   TEXT,
    true_weight_pct REAL,
    size_usd        REAL,
    slot_index      INTEGER,
    eviction_margin REAL,
    scenario        TEXT NOT NULL DEFAULT 'normal',
    recorded_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_date_scenario
    ON position_snapshots (snapshot_date, scenario);

CREATE TABLE IF NOT EXISTS regime_bucket_daily (
    snapshot_date   TEXT NOT NULL,
    scenario        TEXT NOT NULL DEFAULT 'normal',
    regime_bucket   TEXT,
    vix_regime      TEXT,
    val_regime      TEXT,
    final_ceiling_pct REAL,
    formula_text    TEXT,
    recorded_at     TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, scenario)
);

CREATE TABLE IF NOT EXISTS eviction_log (
    snapshot_date   TEXT NOT NULL,
    evicted_ticker  TEXT NOT NULL,
    evicted_function TEXT,
    evicted_interval TEXT,
    challenger_ticker TEXT,
    challenger_score REAL,
    weakest_score   REAL,
    margin_m        REAL,
    mode            TEXT,
    recorded_at     TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, evicted_ticker, evicted_function, evicted_interval)
);

-- Personal book (book_id=personal) has no historical NAV series of its own — this table starts
-- accumulating one from the day the daily job (scripts/run_personal_book_snapshot_daily.py)
-- first runs, same no-backfill rule as the tables above. holdings_json is a point-in-time
-- snapshot of personal_book_service.get_personal_snapshot()['holdings'] for future replay/audit.
CREATE TABLE IF NOT EXISTS personal_book_snapshot_daily (
    snapshot_date   TEXT NOT NULL PRIMARY KEY,
    nav_usd         REAL,
    cash_usd        REAL,
    position_count  INTEGER,
    total_pnl_usd   REAL,
    total_pnl_pct   REAL,
    holdings_json   TEXT,
    recorded_at     TEXT NOT NULL
);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    BOOK_SNAPSHOTS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(BOOK_SNAPSHOTS_DB))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_position_snapshots(
    snapshot_date: str,
    rows: list[dict[str, Any]],
    *,
    scenario: str = "normal",
) -> int:
    """Persist one day's per-position book state. Idempotent — re-running the same date replaces rows."""
    recorded_at = _now_iso()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM position_snapshots WHERE snapshot_date = ? AND scenario = ?",
            (snapshot_date, scenario),
        )
        conn.executemany(
            """
            INSERT INTO position_snapshots (
                snapshot_date, ticker, function, interval, direction,
                sleeve_id, sleeve_label, conviction_tier, conviction_multiplier,
                ssi_ceiling_scalar, regime_bucket, true_weight_pct, size_usd,
                slot_index, eviction_margin, scenario, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot_date,
                    str(r.get("ticker") or ""),
                    r.get("function"),
                    r.get("interval"),
                    r.get("direction"),
                    r.get("sleeve_id"),
                    r.get("sleeve_label"),
                    r.get("conviction_tier"),
                    r.get("conviction_multiplier"),
                    r.get("ssi_ceiling_scalar"),
                    r.get("regime_bucket"),
                    r.get("true_weight_pct"),
                    r.get("size_usd"),
                    r.get("slot_index"),
                    r.get("eviction_margin"),
                    scenario,
                    recorded_at,
                )
                for r in rows
            ],
        )
    return len(rows)


def write_regime_bucket(
    snapshot_date: str,
    *,
    scenario: str = "normal",
    regime_bucket: str | None = None,
    vix_regime: str | None = None,
    val_regime: str | None = None,
    final_ceiling_pct: float | None = None,
    formula_text: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO regime_bucket_daily (
                snapshot_date, scenario, regime_bucket, vix_regime, val_regime,
                final_ceiling_pct, formula_text, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date, scenario) DO UPDATE SET
                regime_bucket=excluded.regime_bucket,
                vix_regime=excluded.vix_regime,
                val_regime=excluded.val_regime,
                final_ceiling_pct=excluded.final_ceiling_pct,
                formula_text=excluded.formula_text,
                recorded_at=excluded.recorded_at
            """,
            (
                snapshot_date, scenario, regime_bucket, vix_regime, val_regime,
                final_ceiling_pct, formula_text, _now_iso(),
            ),
        )


def write_eviction(
    snapshot_date: str,
    *,
    evicted_ticker: str,
    evicted_function: str | None,
    evicted_interval: str | None,
    challenger_ticker: str | None,
    challenger_score: float | None,
    weakest_score: float | None,
    margin_m: float | None,
    mode: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO eviction_log (
                snapshot_date, evicted_ticker, evicted_function, evicted_interval,
                challenger_ticker, challenger_score, weakest_score, margin_m, mode, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date, evicted_ticker, evicted_function, evicted_interval)
            DO UPDATE SET
                challenger_ticker=excluded.challenger_ticker,
                challenger_score=excluded.challenger_score,
                weakest_score=excluded.weakest_score,
                margin_m=excluded.margin_m,
                mode=excluded.mode,
                recorded_at=excluded.recorded_at
            """,
            (
                snapshot_date, evicted_ticker, evicted_function, evicted_interval,
                challenger_ticker, challenger_score, weakest_score, margin_m, mode, _now_iso(),
            ),
        )


def write_personal_book_snapshot(
    snapshot_date: str,
    *,
    nav_usd: float | None,
    cash_usd: float | None,
    position_count: int,
    total_pnl_usd: float | None,
    total_pnl_pct: float | None,
    holdings: list[dict[str, Any]] | None = None,
) -> None:
    """Persist one day's personal-book live snapshot. Idempotent — re-running the same date
    (e.g. a manual re-run, or a second cron trigger) overwrites that day's row rather than
    duplicating it."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO personal_book_snapshot_daily (
                snapshot_date, nav_usd, cash_usd, position_count, total_pnl_usd,
                total_pnl_pct, holdings_json, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date) DO UPDATE SET
                nav_usd=excluded.nav_usd,
                cash_usd=excluded.cash_usd,
                position_count=excluded.position_count,
                total_pnl_usd=excluded.total_pnl_usd,
                total_pnl_pct=excluded.total_pnl_pct,
                holdings_json=excluded.holdings_json,
                recorded_at=excluded.recorded_at
            """,
            (
                snapshot_date, nav_usd, cash_usd, position_count, total_pnl_usd,
                total_pnl_pct, json.dumps(holdings or []), _now_iso(),
            ),
        )


def read_personal_book_series(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM personal_book_snapshot_daily WHERE 1=1"
    params: list[Any] = []
    if start_date:
        query += " AND snapshot_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND snapshot_date <= ?"
        params.append(end_date)
    query += " ORDER BY snapshot_date"
    with _connect() as conn:
        cur = conn.execute(query, params)
        cols = [d[0] for d in cur.description]
        rows = [_row_to_dict(cols, r) for r in cur.fetchall()]
    for row in rows:
        try:
            row["holdings"] = json.loads(row.pop("holdings_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            row["holdings"] = []
    return rows


def earliest_personal_snapshot_date() -> str | None:
    with _connect() as conn:
        cur = conn.execute("SELECT MIN(snapshot_date) FROM personal_book_snapshot_daily")
        result = cur.fetchone()
        return result[0] if result and result[0] else None


def _row_to_dict(cols: list[str], row: tuple) -> dict[str, Any]:
    return dict(zip(cols, row))


def read_position_snapshots(
    snapshot_date: str,
    *,
    scenario: str = "normal",
) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT * FROM position_snapshots WHERE snapshot_date = ? AND scenario = ? ORDER BY ticker",
            (snapshot_date, scenario),
        )
        cols = [d[0] for d in cur.description]
        return [_row_to_dict(cols, r) for r in cur.fetchall()]


def read_regime_bucket_series(
    *,
    scenario: str = "normal",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM regime_bucket_daily WHERE scenario = ?"
    params: list[Any] = [scenario]
    if start_date:
        query += " AND snapshot_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND snapshot_date <= ?"
        params.append(end_date)
    query += " ORDER BY snapshot_date"
    with _connect() as conn:
        cur = conn.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [_row_to_dict(cols, r) for r in cur.fetchall()]


def read_evictions(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM eviction_log WHERE 1=1"
    params: list[Any] = []
    if start_date:
        query += " AND snapshot_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND snapshot_date <= ?"
        params.append(end_date)
    query += " ORDER BY snapshot_date"
    with _connect() as conn:
        cur = conn.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [_row_to_dict(cols, r) for r in cur.fetchall()]


def earliest_snapshot_date() -> str | None:
    """First date this store has any position snapshot — the going-forward boundary."""
    with _connect() as conn:
        cur = conn.execute("SELECT MIN(snapshot_date) FROM position_snapshots")
        result = cur.fetchone()
        return result[0] if result and result[0] else None


def snapshot_status() -> dict[str, Any]:
    earliest = earliest_snapshot_date()
    with _connect() as conn:
        cur = conn.execute("SELECT MAX(snapshot_date), COUNT(DISTINCT snapshot_date) FROM position_snapshots")
        latest, day_count = cur.fetchone()
    return {
        "earliest_snapshot_date": earliest,
        "latest_snapshot_date": latest,
        "days_captured": day_count or 0,
        "db_path": str(BOOK_SNAPSHOTS_DB),
        "note": (
            "No backfill before earliest_snapshot_date — books started capturing from that "
            "date forward per policy; downstream consumers must disclose this boundary."
        ),
    }
