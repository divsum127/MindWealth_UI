"""Percentile rank engine with variable-specific history windows."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.models import SignalTier


def _window_slice(series: pd.Series, var_cfg: dict[str, Any], as_of: pd.Timestamp) -> pd.Series:
    hist = series.loc[:as_of].dropna()
    window = var_cfg.get("pctile_window", "rolling_3y")
    start = var_cfg.get("pctile_start")
    if start:
        hist = hist[hist.index >= pd.Timestamp(start)]
    if window == "rolling_3y":
        cutoff = as_of - pd.DateOffset(years=3)
        hist = hist[hist.index >= cutoff]
    return hist


def percentile_rank(value: float, history: pd.Series) -> float | None:
    """True percentile rank: share of history at or below ``value`` (0–100).

    This is **not** min–max range scaling ``(value - min) / (max - min) * 100``.
    Outliers in the window affect rank only through their count, not by compressing
    the scale between min and max.
    """
    if history.empty or np.isnan(value):
        return None
    arr = history.values.astype(float)
    return float((arr <= value).sum() / len(arr) * 100)


def compute_unconditional_pctile(
    series: pd.Series,
    var_cfg: dict[str, Any],
    as_of: pd.Timestamp,
) -> float | None:
    """Full-history percentile for combo detection (Layer 1)."""
    hist = series.loc[:as_of].dropna()
    start = var_cfg.get("pctile_start")
    if start:
        hist = hist[hist.index >= pd.Timestamp(start)]
    window = var_cfg.get("pctile_window", "rolling_3y")
    if window == "rolling_3y":
        cutoff = as_of - pd.DateOffset(years=3)
        hist = hist[hist.index >= cutoff]
    if hist.empty:
        return None
    val = float(hist.iloc[-1])
    return percentile_rank(val, hist)


def compute_regime_pctile(
    series: pd.Series,
    var_cfg: dict[str, Any],
    as_of: pd.Timestamp,
    fed_cycle: str | None,
) -> tuple[float | None, bool]:
    """Fed-cycle-conditioned percentile; fallback if < min regime days."""
    from src.macro_intelligence.config import load_config

    hist = series.loc[:as_of].dropna()
    if hist.empty or not fed_cycle:
        return compute_unconditional_pctile(series, var_cfg, as_of), True
    from src.macro_intelligence.engine.fed_cycle import fed_cycle_dates_matching

    regime_dates = fed_cycle_dates_matching(fed_cycle)
    if len(regime_dates) < 10:
        with __import__(
            "src.macro_intelligence.db.connection", fromlist=["get_connection"]
        ).get_connection() as conn:
            rows = conn.execute(
                """
                SELECT date FROM macro_regime_log
                WHERE json_extract(regime_json, '$.fed_cycle') = ?
                """,
                (fed_cycle,),
            ).fetchall()
        regime_dates = {pd.Timestamp(r["date"]) for r in rows}
    if len(regime_dates) < load_config().get("regime", {}).get("min_regime_days_for_pctile", 50):
        return compute_unconditional_pctile(series, var_cfg, as_of), True
    regime_hist = hist[hist.index.isin(regime_dates)]
    if len(regime_hist) < 10:
        return compute_unconditional_pctile(series, var_cfg, as_of), True
    val = float(hist.iloc[-1])
    return percentile_rank(val, regime_hist), False


def compute_pctile_for_series(
    series: pd.Series,
    var_cfg: dict[str, Any],
    as_of: pd.Timestamp,
) -> float | None:
    """Backward-compatible: unconditional for combo detection."""
    return compute_unconditional_pctile(series, var_cfg, as_of)


def combo_pctile_from_reading(reading: dict[str, Any] | None) -> float | None:
    if not reading:
        return None
    return reading.get("unconditional_pctile") or reading.get("pctile_rank_3yr")


def evaluate_variable_tier(
    var_id: str,
    var_cfg: dict[str, Any],
    raw: float,
    pctile: float | None,
    meta: dict[str, Any] | None = None,
) -> tuple[SignalTier, str | None]:
    meta = meta or {}
    rare = var_cfg.get("rare", {})
    extreme = var_cfg.get("extreme", {})
    paradigm = var_cfg.get("paradigm", "ROC")
    direction: str | None = None

    def _tier_from_pctile(p: float | None, low: float, high: float) -> SignalTier | None:
        if p is None:
            return None
        if p >= high:
            return SignalTier.EXTREME
        if p <= low:
            return SignalTier.EXTREME
        if p >= 80 or p <= 20:
            return SignalTier.RARE
        return None

    if var_id == "VIX":
        if raw >= extreme.get("abs_level", 35) and pctile and pctile >= extreme.get("high_pctile", 95):
            return SignalTier.EXTREME, "UP"
        if raw >= rare.get("abs_level", 25) and pctile and pctile >= rare.get("high_pctile", 80):
            return SignalTier.RARE, "UP"
        # T-03 fix (2026-06-06 audit): escalate on single-day spike magnitude alone, regardless
        # of absolute level/percentile — e.g. a 40% one-day jump (15.40 -> 21.51) is historically
        # significant stress even though 21.51 sits below the RARE abs_level (25.0).
        day_chg = meta.get("single_day_pct_change")
        if day_chg is not None:
            if day_chg >= extreme.get("single_day_pct_change", 0.40):
                return SignalTier.EXTREME, "UP"
            if day_chg >= rare.get("single_day_pct_change", 0.25):
                return SignalTier.RARE, "UP"
        return SignalTier.NORMAL, None

    if var_id == "HY":
        if raw >= extreme.get("abs_bps", 500) or (pctile and pctile >= 95):
            return SignalTier.EXTREME, "UP"
        if raw >= rare.get("abs_bps", 400) or (pctile and pctile >= 80):
            return SignalTier.RARE, "UP"
        return SignalTier.NORMAL, None

    if var_id == "VXTS":
        if raw >= extreme.get("high_ratio", 1.20) or raw <= extreme.get("low_ratio", 0.85):
            return SignalTier.EXTREME, "UP" if raw > 1 else "DOWN"
        if raw >= rare.get("high_ratio", 1.10) or raw <= rare.get("low_ratio", 0.95):
            return SignalTier.RARE, "UP" if raw > 1 else "DOWN"
        return SignalTier.NORMAL, None

    if var_id == "CAPE":
        if raw >= extreme.get("high_level", 32):
            return SignalTier.EXTREME, "UP"
        if raw <= extreme.get("low_level", 12):
            return SignalTier.EXTREME, "DOWN"
        if raw >= rare.get("high_level", 28):
            return SignalTier.RARE, "UP"
        if raw <= rare.get("low_level", 16):
            return SignalTier.RARE, "DOWN"
        return SignalTier.NORMAL, None

    if var_id == "CURVE":
        steep = meta.get("steepen_4wk", 0)
        spread = raw
        if spread <= extreme.get("spread_bps", -80) or steep >= extreme.get("steepen_4wk_bps", 40):
            return SignalTier.EXTREME, "DOWN" if spread < 0 else "UP"
        if spread <= rare.get("spread_bps", -30) or steep >= rare.get("steepen_4wk_bps", 15):
            return SignalTier.RARE, "DOWN" if spread < 0 else "UP"
        return SignalTier.NORMAL, None

    if var_id == "CFTC":
        if pctile is not None:
            if pctile <= extreme.get("low_pctile", 5) or pctile >= extreme.get("high_pctile", 95):
                return SignalTier.EXTREME, "DOWN" if pctile <= 50 else "UP"
            if pctile <= rare.get("low_pctile", 15) or pctile >= rare.get("high_pctile", 85):
                return SignalTier.RARE, "DOWN" if pctile <= 50 else "UP"
        return SignalTier.NORMAL, None

    if var_id in ("WTI", "CNH", "GSR", "WALCL"):
        thresh_r = rare.get("pct_4wk") or rare.get("mom_pct", 0)
        thresh_e = extreme.get("pct_4wk") or extreme.get("mom_pct", 0)
        if abs(raw) >= thresh_e:
            return SignalTier.EXTREME, "UP" if raw > 0 else "DOWN"
        if abs(raw) >= thresh_r:
            return SignalTier.RARE, "UP" if raw > 0 else "DOWN"
        return SignalTier.NORMAL, None

    if var_id == "NFCI":
        if pctile and pctile >= 95:
            return SignalTier.EXTREME, "UP"
        if pctile and pctile >= 80:
            return SignalTier.RARE, "UP"
        if pctile and pctile <= 5:
            return SignalTier.EXTREME, "DOWN"
        if pctile and pctile <= 20:
            return SignalTier.RARE, "DOWN"
        return SignalTier.NORMAL, None

    if var_id == "CPI":
        if abs(raw) >= extreme.get("surprise_pp", 0.4):
            return SignalTier.EXTREME, "UP" if raw > 0 else "DOWN"
        if abs(raw) >= rare.get("surprise_pp", 0.2):
            return SignalTier.RARE, "UP" if raw > 0 else "DOWN"
        return SignalTier.NORMAL, None

    t = _tier_from_pctile(pctile, 20, 80)
    if t:
        direction = "UP" if pctile and pctile >= 50 else "DOWN"
        return t, direction
    return SignalTier.NORMAL, None
