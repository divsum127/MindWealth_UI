"""Shadow v2 regime labels (Parts A/F) — not production until experiment sign-off."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.macro_intelligence.data.fred_pull import fetch_dff, fetch_fred_series
from src.macro_intelligence.engine.fed_cycle import (
    _change_over,
    _load_dff_daily,
    _load_walcl_mom_weekly,
    _qe_qt_override,
    build_fed_cycle_series,
)
from src.macro_intelligence.config import load_config

# Module-level caches — backfill touches ~1900 Fridays; avoid repeated FRED pulls.
_curve_hist_cache: pd.Series | None = None
_dgs2_cache: pd.Series | None = None
_dff_cache: pd.Series | None = None


def _curve_hist() -> pd.Series:
    global _curve_hist_cache
    if _curve_hist_cache is None:
        _curve_hist_cache = fetch_fred_series("T10Y2Y", "1990-01-01")
    return _curve_hist_cache


def _dgs2_series() -> pd.Series:
    global _dgs2_cache
    if _dgs2_cache is None:
        _dgs2_cache = fetch_fred_series("DGS2", "1990-01-01").astype(float)
    return _dgs2_cache


def _dff_series() -> pd.Series:
    global _dff_cache
    if _dff_cache is None:
        _dff_cache = _load_dff_daily()
    return _dff_cache


def clear_regime_v2_caches() -> None:
    global _curve_hist_cache, _dgs2_cache, _dff_cache
    _curve_hist_cache = _dgs2_cache = _dff_cache = None


def collapse_fed_cycle_v2(legacy_label: str) -> str:
    """Map 7-state fed_cycle → 4-state v2 (QE/QT → liquidity flag only)."""
    u = (legacy_label or "").upper()
    if u in ("HIKING_EARLY", "HIKING_LATE", "TIGHTENING"):
        return "TIGHTENING"
    if u in ("CUTTING_EARLY",):
        return "PIVOTING"
    if u in ("CUTTING_LATE",):
        return "EASING"
    if u in ("PAUSING", "PAUSE"):
        return "EASY"
    if u in ("QE", "QT"):
        return "EASY"
    return "EASY"


def liquidity_v2(nfci: float | None, walcl_mom: float | None) -> str:
    """4-state liquidity: easy/tight × improving/tightening."""
    cfg = load_config().get("regime", {})
    easy = (nfci or 0) <= float(cfg.get("nfci_easy_max", -0.3))
    tight = (nfci or 0) >= float(cfg.get("nfci_tight_min", 0.3))
    if not easy and not tight:
        level = "NEUTRAL"
    else:
        level = "EASY" if easy else "TIGHT"
    if walcl_mom is None:
        direction = "FLAT"
    elif walcl_mom > 0.3:
        direction = "IMPROVING"
    elif walcl_mom < -0.3:
        direction = "TIGHTENING"
    else:
        direction = "FLAT"
    if level == "NEUTRAL":
        return f"NEUTRAL_{direction}"
    return f"{level}_{direction}"


def curve_regime_f2(
    spread_bps: float | None,
    steepen_4wk_bps: float | None,
    inverted_weeks: int = 0,
) -> str:
    """F2/F2a: INVERTED requires <0 for 4+ weeks; STEEPENING post-trough rules."""
    if spread_bps is None:
        return "NORMAL"
    if inverted_weeks >= 4 and spread_bps < 0:
        if steepen_4wk_bps is not None and steepen_4wk_bps >= 40:
            return "STEEPENING"
        if steepen_4wk_bps is not None and steepen_4wk_bps >= 15:
            return "STEEPENING"
        return "INVERTED"
    if spread_bps < 30 and spread_bps >= 0:
        return "FLAT"
    if steepen_4wk_bps is not None and steepen_4wk_bps >= 15:
        return "STEEPENING"
    return "NORMAL"


def count_inverted_weeks(curve_series: pd.Series, as_of: pd.Timestamp) -> int:
    """Consecutive weeks with T10Y2Y < 0 ending at as_of."""
    weekly = curve_series.resample("W-FRI").last().loc[:as_of].dropna()
    if weekly.empty:
        return 0
    count = 0
    for v in reversed(weekly.values):
        if v < 0:
            count += 1
        else:
            break
    return count


def is_hiking_period(as_of: pd.Timestamp, dff: pd.Series | None = None) -> bool:
    """F3: FFR rising and cumulative hike cycle > 100bps."""
    dff = dff if dff is not None else _dff_series()
    rate = dff.loc[:as_of].dropna()
    if len(rate) < 2:
        return False
    year_ago = as_of - pd.Timedelta(days=365)
    past = rate.loc[:year_ago]
    if past.empty:
        return False
    cumulative = float(rate.iloc[-1]) - float(past.iloc[-1])
    chg_13w = _change_over(dff, as_of, 13)
    return chg_13w > 0.25 and cumulative > 1.0


def tightening_late_f1(as_of: pd.Timestamp, curve_bps: float | None) -> bool:
    """F1 TIGHTENING-LATE quant rule."""
    dff = _dff_series()
    rate = dff.loc[:as_of].dropna()
    if rate.empty:
        return False
    ffr = float(rate.iloc[-1])
    year_ago = as_of - pd.Timedelta(days=365)
    past = rate.loc[:year_ago]
    rise = ffr - float(past.iloc[-1]) if not past.empty else 0
    curve_ok = (curve_bps or 0) < -30
    chg_4 = _change_over(dff, as_of, 4)
    decel = chg_4 < 0.1
    return ffr > 3.5 and rise > 1.5 and (curve_ok or decel)


def geo_overlay_v2(date_str: str) -> str:
    """Rule-based 3-state geo (no Claude batch in experiments)."""
    ts = pd.Timestamp(date_str)
    if pd.Timestamp("2020-02-01") <= ts <= pd.Timestamp("2020-06-30"):
        return "CRISIS"
    if pd.Timestamp("2022-02-01") <= ts <= pd.Timestamp("2022-04-30"):
        return "ELEVATED_RISK"
    if pd.Timestamp("2025-02-01") <= ts <= pd.Timestamp("2025-04-30"):
        return "ELEVATED_RISK"
    return "NEUTRAL"


def build_regime_v2(as_of: str, readings: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    from src.macro_intelligence.data.pull_all import get_readings_as_of
    from src.macro_intelligence.engine.regime_rules import build_python_regime

    readings = readings or get_readings_as_of(as_of)
    legacy = build_python_regime(as_of, readings)
    curve = readings.get("CURVE", {})
    spread = curve.get("raw_value")
    meta: dict[str, Any] = {}
    try:
        meta = json.loads(curve.get("meta_json") or "{}")
    except Exception:
        pass
    steepen = meta.get("steepen_4wk_bps") or meta.get("steepen_4wk")
    nfci = readings.get("NFCI", {}).get("raw_value")
    walcl = readings.get("WALCL", {}).get("raw_value")
    cape = readings.get("CAPE", {}).get("raw_value")

    ts = pd.Timestamp(as_of)
    curve_hist = _curve_hist()
    inv_weeks = count_inverted_weeks(curve_hist, ts)

    fed_legacy = legacy.get("fed_cycle", "PAUSING")
    cfg = load_config().get("regime", {})
    qe_qt = _qe_qt_override(walcl, cfg)

    regime = {
        "fed_cycle_v2": collapse_fed_cycle_v2(fed_legacy),
        "fed_cycle_legacy": fed_legacy,
        "curve_regime_v2": curve_regime_f2(spread, steepen, inv_weeks),
        "curve_regime_legacy": legacy.get("curve_regime"),
        "val_regime": legacy.get("val_regime"),
        "liquidity_v2": liquidity_v2(nfci, walcl),
        "liquidity_legacy": legacy.get("liquidity"),
        "geo_overlay_v2": geo_overlay_v2(as_of),
        "geo_overlay": legacy.get("geo_overlay", "NEUTRAL"),
        "balance_sheet_policy": qe_qt,
        "inverted_weeks": inv_weeks,
        "hiking_period_f3": is_hiking_period(ts),
        "tightening_late_f1": tightening_late_f1(ts, spread),
        "cape_level": cape,
    }
    return regime


def twy_roc_at_date(as_of: str) -> dict[str, Any]:
    """Part B: DGS2 56-calendar-day change in pp."""
    dgs2 = _dgs2_series()
    ts = pd.Timestamp(as_of)
    today = dgs2.loc[:ts].dropna()
    if today.empty:
        return {"twy_roc_pp": None, "direction": None}
    prior = ts - pd.Timedelta(days=56)
    past = dgs2.loc[:prior].dropna()
    if past.empty:
        return {"twy_roc_pp": None, "direction": None}
    delta = float(today.iloc[-1]) - float(past.iloc[-1])
    if delta > 0.30:
        direction = "HAWKISH"
    elif delta < -0.30:
        direction = "DOVISH"
    else:
        direction = "NEUTRAL"
    return {"twy_roc_pp": round(delta, 4), "direction": direction, "dgs2": float(today.iloc[-1])}
