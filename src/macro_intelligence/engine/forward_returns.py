"""SPX forward returns after combo fires."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pandas_market_calendars as mcal

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.db.connection import get_connection

_HORIZONS = {
    "spx_1w": 5,
    "spx_2w": 10,
    "spx_1m": 21,
    "spx_3m": 63,
    "spx_6m": 126,
    "spx_9m": 189,
    "spx_12m": 252,
}
_SESSIONS_CACHE: pd.DatetimeIndex | None = None


def _nyse_sessions() -> pd.DatetimeIndex:
    """Cached NYSE session index (avoids per-row calendar.schedule calls)."""
    global _SESSIONS_CACHE
    if _SESSIONS_CACHE is not None:
        return _SESSIONS_CACHE
    cal = mcal.get_calendar("NYSE")
    schedule = cal.schedule(start_date="1990-01-01", end_date=datetime.now() + pd.Timedelta(days=400))
    _SESSIONS_CACHE = schedule.index.tz_localize(None)
    return _SESSIONS_CACHE


def forward_return_pct(
    spx: pd.Series,
    fire_date: pd.Timestamp,
    trading_days: int,
    sessions: pd.DatetimeIndex | None = None,
) -> float | None:
    sessions = sessions if sessions is not None else _nyse_sessions()
    fire_date = pd.Timestamp(fire_date).tz_localize(None)
    idx = sessions.searchsorted(fire_date, side="left")
    if idx >= len(sessions) or sessions[idx] < fire_date:
        idx += 1
    if idx + trading_days >= len(sessions):
        return None
    end_date = sessions[idx + trading_days]
    spx = spx.sort_index()
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    # Return None if the required forward window exceeds available price data
    spx_last_date = spx.index[-1] if not spx.empty else None
    if spx_last_date is None or end_date > spx_last_date:
        return None
    start_slice = spx.loc[:fire_date]
    if start_slice.empty:
        return None
    start_px = float(start_slice.iloc[-1])
    end_slice = spx.loc[end_date:end_date]
    if end_slice.empty:
        end_slice = spx.loc[:end_date]
    if end_slice.empty:
        return None
    end_px = float(end_slice.iloc[-1])
    return float((end_px - start_px) / start_px * 100)


def compute_forward_returns_for_combo(
    combo_id: int,
    fire_date: str,
    spx: pd.Series | None = None,
    sessions: pd.DatetimeIndex | None = None,
) -> dict[str, float | None]:
    cfg = load_config()
    ticker = cfg.get("forward_returns", {}).get("spx_ticker", "^GSPC")
    if spx is None:
        spx = fetch_yahoo_close(ticker, "1990-01-01")
    fire_ts = pd.Timestamp(fire_date)
    out: dict[str, float | None] = {}
    for col, days in _HORIZONS.items():
        out[col] = forward_return_pct(spx, fire_ts, days, sessions=sessions)
    return out


def backfill_forward_returns(*, log_every: int = 200) -> int:
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()
    count = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.combo_id, cf.date FROM combo_fires cf
            LEFT JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE fr.combo_id IS NULL OR fr.spx_3m IS NULL
            """
        ).fetchall()
        total = len(rows)
        print(f"forward_returns: {total} combo fires to fill", flush=True)
        for i, row in enumerate(rows, 1):
            rets = compute_forward_returns_for_combo(
                row["combo_id"], row["date"], spx, sessions=sessions
            )
            conn.execute(
                """
                INSERT INTO forward_returns (combo_id, spx_1w, spx_2w, spx_1m, spx_3m, spx_6m, spx_9m, spx_12m)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(combo_id) DO UPDATE SET
                  spx_1w=excluded.spx_1w, spx_2w=excluded.spx_2w,
                  spx_1m=excluded.spx_1m, spx_3m=excluded.spx_3m, spx_6m=excluded.spx_6m,
                  spx_9m=excluded.spx_9m, spx_12m=excluded.spx_12m
                """,
                (
                    row["combo_id"],
                    rets.get("spx_1w"),
                    rets.get("spx_2w"),
                    rets.get("spx_1m"),
                    rets.get("spx_3m"),
                    rets.get("spx_6m"),
                    rets.get("spx_9m"),
                    rets.get("spx_12m"),
                ),
            )
            count += 1
            if log_every and i % log_every == 0:
                conn.commit()
                print(f"  ... {i}/{total} forward returns", flush=True)
    return count


def backfill_extended_returns(*, log_every: int = 500) -> int:
    """Fill spx_9m and spx_12m for rows that already have shorter horizons."""
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()
    count = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.combo_id, cf.date, fr.spx_9m, fr.spx_12m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE fr.spx_9m IS NULL OR fr.spx_12m IS NULL
            """
        ).fetchall()
        total = len(rows)
        print(f"extended forward_returns: {total} rows to fill", flush=True)
        for i, row in enumerate(rows, 1):
            fire_ts = pd.Timestamp(row["date"])
            spx_9m = (
                forward_return_pct(spx, fire_ts, _HORIZONS["spx_9m"], sessions=sessions)
                if row["spx_9m"] is None
                else row["spx_9m"]
            )
            spx_12m = (
                forward_return_pct(spx, fire_ts, _HORIZONS["spx_12m"], sessions=sessions)
                if row["spx_12m"] is None
                else row["spx_12m"]
            )
            conn.execute(
                """
                UPDATE forward_returns SET spx_9m = ?, spx_12m = ?
                WHERE combo_id = ?
                """,
                (spx_9m, spx_12m, row["combo_id"]),
            )
            count += 1
            if log_every and i % log_every == 0:
                conn.commit()
                print(f"  ... {i}/{total} extended returns", flush=True)
    return count


def fill_matured_returns(as_of: str | None = None) -> int:
    """Update NULL forward return fields when horizons have elapsed."""
    return backfill_forward_returns()
