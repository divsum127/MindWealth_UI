"""CFTC positioning pattern flags (display/alert only — not sizing gates)."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.cftc_pull import fetch_cftc_fast_money_net
from src.macro_intelligence.data.source_freshness import check_cftc_freshness


def _pattern_cfg() -> dict[str, Any]:
    return load_config().get("cftc", {})


def _detect_positioning_pattern(
    fm_pctile: float | None,
    rm_pctile: float | None,
) -> str:
    if fm_pctile is None or rm_pctile is None:
        return "none"
    patterns = _pattern_cfg().get("positioning_patterns", {})
    squeeze = patterns.get("squeeze", {})
    liq = patterns.get("liquidity_exit", {})
    fm_max = float(squeeze.get("fm_pctile_max", 20))
    rm_min = float(squeeze.get("rm_pctile_min", 45))
    rm_max = float(liq.get("rm_pctile_max", 30))
    fm_min = float(liq.get("fm_pctile_min", 60))
    if fm_pctile < fm_max and rm_pctile > rm_min:
        return "squeeze"
    if rm_pctile < rm_max and fm_pctile > fm_min:
        return "liquidity_exit"
    return "none"


def evaluate_cftc_positioning(
    fm_pctile: float | None,
    rm_pctile: float | None,
    as_of: str,
    *,
    fm_net: float | None = None,
    rm_net: float | None = None,
) -> dict[str, Any]:
    """Freshness + Squeeze/Liquidity Exit pattern for Layer 3 COT display."""
    cfg = _pattern_cfg()
    templates = cfg.get("pattern_templates", {})
    pending_status = cfg.get("pending_status", "PENDING_CFTC_CONFIRM")
    freshness_row = check_cftc_freshness(as_of, fetch_cftc_fast_money_net())
    stale = bool(freshness_row.stale)
    data_freshness = "waiting_for_friday_release" if stale else "current"
    status = pending_status if stale else "CONFIRMED"
    pattern = _detect_positioning_pattern(fm_pctile, rm_pctile)
    squeeze_setup = pattern == "squeeze"
    liquidity_exit = pattern == "liquidity_exit"
    pattern_label = {
        "squeeze": "Squeeze",
        "liquidity_exit": "Liquidity Exit",
        "none": "None",
    }.get(pattern, "None")
    plain_english = templates.get(pattern, "") if pattern != "none" else ""
    position_date = freshness_row.source_date
    expected_release = freshness_row.expected_source_date
    next_release: str | None = None
    release_date: str | None = None
    if position_date and expected_release:
        import pandas as pd

        pos_ts = pd.Timestamp(position_date)
        release_date = (pos_ts + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        exp_ts = pd.Timestamp(expected_release) + pd.Timedelta(days=3)
        next_release = exp_ts.strftime("%Y-%m-%d")
    return {
        "fm_net": fm_net,
        "rm_net": rm_net,
        "fm_pctile": fm_pctile,
        "rm_pctile": rm_pctile,
        "status": status,
        "data_freshness": data_freshness,
        "positioning_pattern": None if pattern == "none" else pattern,
        "squeeze_setup": squeeze_setup,
        "liquidity_exit": liquidity_exit,
        "pattern_label": pattern_label,
        "plain_english": plain_english,
        "position_date": position_date,
        "release_date": release_date,
        "expected_release": expected_release,
        "next_release": next_release,
        "stale": stale,
    }
