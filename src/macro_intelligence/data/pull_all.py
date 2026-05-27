"""Orchestrate all 12 variable data pulls into daily_readings."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.cape_scrape import load_cape_series
from src.macro_intelligence.data.cftc_pull import fetch_cftc_fast_money_net
from src.macro_intelligence.data.cpi_pull import load_cpi_surprises
from src.macro_intelligence.data.fred_pull import curve_features, fetch_fred_series, walcl_mom_pct
from src.macro_intelligence.data.yahoo_pull import (
    fetch_yahoo_close,
    gsr_ratio,
    rolling_pct_change,
    spx_with_50wma,
    vix_term_structure,
)
from src.macro_intelligence.db.connection import get_connection

_CACHE: dict[str, pd.Series | pd.DataFrame] = {}


def _cache_key(name: str) -> str:
    return name


def load_all_series(force: bool = False) -> dict[str, Any]:
    if _CACHE and not force:
        return _CACHE

    nfci = fetch_fred_series("NFCI", "1973-01-01")
    hy = fetch_fred_series("BAMLH0A0HYM2", "1996-01-01")
    walcl = fetch_fred_series("WALCL", "2003-01-01")
    curve = fetch_fred_series("T10Y2Y", "1976-01-01")
    vix = fetch_yahoo_close("^VIX", "1990-01-01")
    vxts = vix_term_structure("2007-01-01")
    wti = fetch_yahoo_close("CL=F", "1985-01-01")
    cnh = fetch_yahoo_close("USDCNH=X", "2010-01-01")
    gsr = gsr_ratio("1990-01-01")
    cape = load_cape_series()
    cftc = fetch_cftc_fast_money_net(2006)
    cpi = load_cpi_surprises()
    spx_w = spx_with_50wma("1990-01-01")

    _CACHE.clear()
    _CACHE.update(
        {
            "NFCI": nfci,
            "HY": hy,
            "WALCL": walcl_mom_pct(walcl),
            "CURVE": curve_features(curve),
            "VIX": vix,
            "VXTS": vxts,
            "WTI": rolling_pct_change(wti, 20),
            "CNH": rolling_pct_change(cnh, 20),
            "GSR": rolling_pct_change(gsr, 20),
            "CAPE": cape,
            "CFTC": cftc,
            "CPI": cpi,
            "SPX_W": spx_w,
        }
    )
    return _CACHE


def pull_all_series(as_of: str | None = None) -> list[dict[str, Any]]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    series = load_all_series()
    cfg = load_config()
    readings: list[dict[str, Any]] = []

    for var_cfg in cfg["variables"]:
        vid = var_cfg["id"]
        reading = _reading_for_var(vid, var_cfg, series, as_of)
        if reading:
            readings.append(reading)
            _upsert_reading(reading)

    return readings


def _reading_for_var(
    vid: str,
    var_cfg: dict[str, Any],
    series: dict[str, Any],
    as_of: str,
) -> dict[str, Any] | None:
    from src.macro_intelligence.engine.percentiles import compute_pctile_for_series, evaluate_variable_tier

    as_of_ts = pd.Timestamp(as_of)

    if vid == "CURVE":
        df: pd.DataFrame = series.get("CURVE")  # type: ignore[assignment]
        if df is None or df.empty:
            return None
        row = df.loc[:as_of_ts].iloc[-1]
        raw = float(row["spread_bps"])
        pctile = compute_pctile_for_series(df["spread_bps"], var_cfg, as_of_ts)
        tier, direction = evaluate_variable_tier(vid, var_cfg, raw, pctile, meta={"steepen_4wk": float(row.get("steepen_4wk_bps", 0))})
        return _pack(vid, as_of, raw, pctile, tier, direction)

    if vid == "SPX_W":
        return None

    data = series.get(vid)
    if data is None or (hasattr(data, "empty") and data.empty):
        return None

    s: pd.Series = data  # type: ignore[assignment]
    hist = s.loc[:as_of_ts]
    if hist.empty:
        return None
    raw = float(hist.iloc[-1])
    pctile = compute_pctile_for_series(s, var_cfg, as_of_ts)
    tier, direction = evaluate_variable_tier(vid, var_cfg, raw, pctile)
    return _pack(vid, as_of, raw, pctile, tier, direction)


def _pack(vid, as_of, raw, pctile, tier, direction) -> dict[str, Any]:
    return {
        "var_id": vid,
        "date": as_of,
        "raw_value": raw,
        "pctile_rank_3yr": pctile,
        "signal_tier": tier.value if hasattr(tier, "value") else tier,
        "direction": direction,
        "meta_json": "{}",
    }


def _upsert_reading(r: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_readings (date, var_id, raw_value, pctile_rank_3yr, signal_tier, direction, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, var_id) DO UPDATE SET
              raw_value=excluded.raw_value,
              pctile_rank_3yr=excluded.pctile_rank_3yr,
              signal_tier=excluded.signal_tier,
              direction=excluded.direction,
              meta_json=excluded.meta_json
            """,
            (
                r["date"],
                r["var_id"],
                r["raw_value"],
                r["pctile_rank_3yr"],
                r["signal_tier"],
                r["direction"],
                r.get("meta_json", "{}"),
            ),
        )


def pull_series_for_date(var_id: str, as_of: str) -> dict[str, Any] | None:
    pull_all_series(as_of)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_readings WHERE var_id=? AND date=?",
            (var_id, as_of),
        ).fetchone()
    return dict(row) if row else None


def get_readings_as_of(as_of: str) -> dict[str, dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM daily_readings WHERE date=?", (as_of,)).fetchall()
    return {r["var_id"]: dict(r) for r in rows}
