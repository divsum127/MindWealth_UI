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
    # An absent leg means "not part of this rule", not "fall back to the old number". The code
    # defaulted rm_pctile_min to 45 and rm_pctile_max to 30, so deleting the RM leg from the
    # config would have quietly kept enforcing it (Rohit 13 Aug: no RM in SQUEEZE).
    if _pattern_matches(squeeze, fm_pctile, rm_pctile):
        return "squeeze"
    if _pattern_matches(liq, fm_pctile, rm_pctile):
        return "liquidity_exit"
    return "none"


def _pattern_matches(
    rule: dict[str, Any],
    fm_pctile: float,
    rm_pctile: float,
) -> bool:
    """True when every leg present in the rule holds. An empty rule never fires."""
    # Boundary convention, from how the cuts are written: "FM<10" is strict on the max legs,
    # "LIQUIDITY EXIT display >=80" is inclusive on the min legs.
    legs = (
        ("fm_pctile_max", fm_pctile, lambda v, t: v < t),
        ("fm_pctile_min", fm_pctile, lambda v, t: v >= t),
        ("rm_pctile_max", rm_pctile, lambda v, t: v < t),
        ("rm_pctile_min", rm_pctile, lambda v, t: v >= t),
    )
    present = [(value, float(rule[key]), test) for key, value, test in legs if rule.get(key) is not None]
    if not present:
        return False
    return all(test(value, threshold) for value, threshold, test in present)


def pattern_rules() -> dict[str, dict[str, float]]:
    """The active cuts, published so the UI can describe the rule it is actually showing.

    The Sentiment page used to hardcode "FM <20th - RM >45th pct" under the flag rows; when the
    cuts changed the page kept describing the old rule.
    """
    patterns = _pattern_cfg().get("positioning_patterns", {})
    out: dict[str, dict[str, float]] = {}
    for name in ("squeeze", "liquidity_exit"):
        rule = patterns.get(name) or {}
        out[name] = {k: float(v) for k, v in rule.items() if v is not None}
    return out


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
        # `next_release` used to be expected_release + 3 days. expected_release is the latest
        # Tuesday whose report is already due, so +3 lands on the Friday that has ALREADY
        # happened -- the tile advertised "next release Fri 14 Aug" on 18 Aug. CFTC publishes
        # weekly, so the next one is the first Friday strictly after the as-of date.
        next_ts = pd.Timestamp(release_date)
        as_of_ts = pd.Timestamp(as_of).normalize()
        while next_ts <= as_of_ts:
            next_ts += pd.Timedelta(days=7)
        next_release = next_ts.strftime("%Y-%m-%d")
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
