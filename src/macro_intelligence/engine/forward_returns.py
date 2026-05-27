"""SPX forward returns after combo fires."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pandas_market_calendars as mcal

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.db.connection import get_connection

_HORIZONS = {"spx_1w": 5, "spx_2w": 10, "spx_1m": 21, "spx_3m": 63, "spx_6m": 126}


def _trading_calendar():
    return mcal.get_calendar("NYSE")


def forward_return_pct(spx: pd.Series, fire_date: pd.Timestamp, trading_days: int) -> float | None:
    cal = _trading_calendar()
    schedule = cal.schedule(start_date=fire_date - pd.Timedelta(days=5), end_date=fire_date + pd.Timedelta(days=400))
    sessions = schedule.index.tz_localize(None)
    sessions = sessions[sessions >= fire_date]
    if len(sessions) <= trading_days:
        return None
    end_date = sessions[trading_days]
    spx = spx.copy()
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    start_px = spx.loc[:fire_date].iloc[-1] if not spx.loc[:fire_date].empty else None
    end_slice = spx.loc[:end_date]
    if start_px is None or end_slice.empty:
        return None
    end_px = end_slice.iloc[-1]
    return float((end_px - start_px) / start_px * 100)


def compute_forward_returns_for_combo(combo_id: int, fire_date: str, spx: pd.Series | None = None) -> dict[str, float | None]:
    cfg = load_config()
    ticker = cfg.get("forward_returns", {}).get("spx_ticker", "^GSPC")
    if spx is None:
        spx = fetch_yahoo_close(ticker, "1990-01-01")
    fire_ts = pd.Timestamp(fire_date)
    out: dict[str, float | None] = {}
    for col, days in _HORIZONS.items():
        out[col] = forward_return_pct(spx, fire_ts, days)
    return out


def backfill_forward_returns() -> int:
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    count = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.combo_id, cf.date FROM combo_fires cf
            LEFT JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE fr.combo_id IS NULL OR fr.spx_3m IS NULL
            """
        ).fetchall()
        for row in rows:
            rets = compute_forward_returns_for_combo(row["combo_id"], row["date"], spx)
            conn.execute(
                """
                INSERT INTO forward_returns (combo_id, spx_1w, spx_2w, spx_1m, spx_3m, spx_6m)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(combo_id) DO UPDATE SET
                  spx_1w=excluded.spx_1w, spx_2w=excluded.spx_2w,
                  spx_1m=excluded.spx_1m, spx_3m=excluded.spx_3m, spx_6m=excluded.spx_6m
                """,
                (
                    row["combo_id"],
                    rets.get("spx_1w"),
                    rets.get("spx_2w"),
                    rets.get("spx_1m"),
                    rets.get("spx_3m"),
                    rets.get("spx_6m"),
                ),
            )
            count += 1
    return count


def fill_matured_returns(as_of: str | None = None) -> int:
    """Update NULL forward return fields when horizons have elapsed."""
    return backfill_forward_returns()
