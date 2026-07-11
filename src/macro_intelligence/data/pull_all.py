"""Orchestrate all 12 variable data pulls into daily_readings."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.bls_pull import load_cpi_surprise_series, try_bls_cpi_pull, try_fred_cpi_fallback_if_stale
from src.macro_intelligence.data.cape_scrape import load_cape_series
from src.macro_intelligence.data.cftc_pull import fetch_cftc_fast_money_net, persist_cftc_snapshot
from src.macro_intelligence.data.source_freshness import ensure_cape_cftc_fresh, get_last_freshness_audit, latest_observation_as_of
from src.macro_intelligence.data.cpi_pull import load_cpi_surprises
from src.macro_intelligence.data.fred_pull import curve_features, fetch_fred_series, walcl_mom_pct
from src.macro_intelligence.data.yahoo_pull import (
    fetch_yahoo_close,
    gsr_ratio,
    calendar_pct_change,
    rolling_pct_change,
    spx_with_50wma,
    vix_term_structure,
)
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.percentiles import (
    compute_pctile_for_series,
    compute_regime_pctile,
    compute_unconditional_pctile,
    evaluate_variable_tier,
)

_CACHE: dict[str, pd.Series | pd.DataFrame] = {}


def load_all_series(force: bool = False, as_of: str | None = None) -> dict[str, Any]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    if _CACHE and not force:
        return _CACHE

    ensure_cape_cftc_fresh(as_of)

    nfci = fetch_fred_series("NFCI", "1973-01-01")
    hy = fetch_fred_series("BAMLH0A0HYM2", "1996-01-01")
    walcl = fetch_fred_series("WALCL", "2003-01-01")
    curve = fetch_fred_series("T10Y2Y", "1976-01-01")
    vix = fetch_yahoo_close("^VIX", "1990-01-01")
    vxts = vix_term_structure("2007-01-01")
    wti = fetch_yahoo_close("CL=F", "1985-01-01")
    if len(wti) < 100:
        # CL=F (WTI futures) rarely fails but FRED DCOILWTICO is the spec fallback (back to 1986).
        wti = fetch_fred_series("DCOILWTICO", "1985-01-01")
    cnh = fetch_yahoo_close("USDCNH=X", "2010-01-01")
    if len(cnh) < 100:
        # Yahoo often returns a single stale USDCNH=X bar; FRED DEXCHUS is the production fallback.
        cnh = fetch_fred_series("DEXCHUS", "2010-01-01")
    gsr = gsr_ratio("1990-01-01")
    cape = load_cape_series()
    cftc = fetch_cftc_fast_money_net(2006)
    try_bls_cpi_pull()
    try_fred_cpi_fallback_if_stale()
    try:
        from src.macro_intelligence.data.macro_calendar import sync_macro_releases_to_db

        sync_macro_releases_to_db()
    except Exception:
        try:
            from src.macro_intelligence.data.investing_cpi_consensus import sync_cpi_releases_to_db

            sync_cpi_releases_to_db()
        except Exception:
            pass
    cpi_db = load_cpi_surprise_series()
    cpi_csv = load_cpi_surprises()
    cpi = cpi_db if not cpi_db.empty else cpi_csv
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
            "WTI": calendar_pct_change(wti, 28),
            "CNH": calendar_pct_change(cnh, 28),
            "GSR": calendar_pct_change(gsr, 28),
            "CAPE": cape,
            "CFTC": cftc,
            "CPI": cpi,
            "SPX_W": spx_w,
        }
    )
    return _CACHE


def pull_all_series(
    as_of: str | None = None,
    fed_cycle: str | None = None,
    *,
    persist_cftc: bool | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    series = load_all_series(as_of=as_of)
    do_cftc = persist_cftc if persist_cftc is not None else datetime.now().weekday() == 4
    if do_cftc:
        persist_cftc_snapshot(as_of)
    cfg = load_config()
    readings: list[dict[str, Any]] = []
    if fed_cycle is None:
        from src.macro_intelligence.engine.regime_rules import build_python_regime

        fed_cycle = build_python_regime(as_of).get("fed_cycle")

    for var_cfg in cfg["variables"]:
        vid = var_cfg["id"]
        reading = _reading_for_var(vid, var_cfg, series, as_of, fed_cycle)
        if reading:
            readings.append(reading)
            _upsert_reading(reading)

    return readings


def pull_all_series_with_audit(
    as_of: str | None = None,
    fed_cycle: str | None = None,
    *,
    persist_cftc: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    readings = pull_all_series(as_of, fed_cycle, persist_cftc=persist_cftc)
    return readings, get_last_freshness_audit()


def _reading_for_var(
    vid: str,
    var_cfg: dict[str, Any],
    series: dict[str, Any],
    as_of: str,
    fed_cycle: str | None,
) -> dict[str, Any] | None:
    as_of_ts = pd.Timestamp(as_of)

    if vid == "CURVE":
        df: pd.DataFrame = series.get("CURVE")  # type: ignore[assignment]
        if df is None or df.empty:
            return None
        row = df.loc[:as_of_ts].iloc[-1]
        raw = float(row["spread_bps"])
        uncond = compute_unconditional_pctile(df["spread_bps"], var_cfg, as_of_ts)
        regime_p, _ = compute_regime_pctile(df["spread_bps"], var_cfg, as_of_ts, fed_cycle)
        tier, direction = evaluate_variable_tier(
            vid, var_cfg, raw, uncond, meta={"steepen_4wk_bps": float(row.get("steepen_4wk_bps", 0))}
        )
        return _pack(vid, as_of, raw, uncond, regime_p, tier, direction, meta={"steepen_4wk_bps": row.get("steepen_4wk_bps")})

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
    uncond = compute_unconditional_pctile(s, var_cfg, as_of_ts)
    regime_p, _ = compute_regime_pctile(s, var_cfg, as_of_ts, fed_cycle)
    tier, direction = evaluate_variable_tier(vid, var_cfg, raw, uncond)
    meta = _variable_source_meta(vid, s, as_of)
    return _pack(vid, as_of, raw, uncond, regime_p, tier, direction, meta=meta)


def _variable_source_meta(vid: str, series: pd.Series, as_of: str) -> dict[str, Any]:
    """Attach source observation date + lag for variables with publication delay."""
    if vid not in ("CAPE", "CFTC"):
        return {}
    src_date, _ = latest_observation_as_of(series, as_of)
    if src_date is None:
        return {"report_date": as_of, "source_date": None, "lag_days": None}
    lag = (pd.Timestamp(as_of) - src_date).days
    meta: dict[str, Any] = {
        "report_date": as_of,
        "source_date": src_date.strftime("%Y-%m-%d"),
        "lag_days": lag,
    }
    if vid == "CFTC":
        from src.macro_intelligence.data.source_freshness import expected_latest_cftc_tuesday

        expected = expected_latest_cftc_tuesday(as_of)
        meta["expected_source_date"] = expected.strftime("%Y-%m-%d")
        meta["source_lags_expected"] = src_date < expected
    return meta


def _pack(vid, as_of, raw, uncond, regime_p, tier, direction, meta=None) -> dict[str, Any]:
    meta = meta or {}
    return {
        "var_id": vid,
        "date": as_of,
        "raw_value": raw,
        "pctile_rank_3yr": uncond,
        "unconditional_pctile": uncond,
        "regime_pctile": regime_p,
        "signal_tier": tier.value if hasattr(tier, "value") else tier,
        "direction": direction,
        "meta_json": json.dumps(meta),
    }


def _upsert_reading(r: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_readings
            (date, var_id, raw_value, pctile_rank_3yr, unconditional_pctile, regime_pctile,
             signal_tier, direction, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, var_id) DO UPDATE SET
              raw_value=excluded.raw_value,
              pctile_rank_3yr=excluded.pctile_rank_3yr,
              unconditional_pctile=excluded.unconditional_pctile,
              regime_pctile=excluded.regime_pctile,
              signal_tier=excluded.signal_tier,
              direction=excluded.direction,
              meta_json=excluded.meta_json
            """,
            (
                r["date"],
                r["var_id"],
                r["raw_value"],
                r["pctile_rank_3yr"],
                r.get("unconditional_pctile"),
                r.get("regime_pctile"),
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
