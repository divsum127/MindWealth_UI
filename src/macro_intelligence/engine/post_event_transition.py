"""Post-event regime transition detection within 48h of scheduled macro events."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.macro_calendar import get_recent_event_in_window
from src.macro_intelligence.data.pull_all import get_readings_as_of, pull_all_series
from src.macro_intelligence.data.yield_window import build_event_metrics, event_window_anchors
from src.macro_intelligence.engine.combo_detector import VAR_IDS, detect_named_combos

INACTIVE_PAYLOAD: dict[str, Any] = {
    "active": False,
    "regime_transition": False,
    "transition_type": None,
    "event": None,
    "hours_since_event": None,
    "variables_crossed": [],
    "combos_changed": False,
    "combo_diff": [],
    "metrics": {},
}


def _scheduled_cfg() -> dict[str, Any]:
    return load_config().get("scheduled_events", {})


def _tier_is_rare(tier: str | None) -> bool:
    return tier in ("RARE", "EXTREME")


def crossed_rare_boundary(pre: dict[str, Any], post: dict[str, Any]) -> bool:
    pre_tier = pre.get("signal_tier", "NORMAL")
    post_tier = post.get("signal_tier", "NORMAL")
    if _tier_is_rare(pre_tier) != _tier_is_rare(post_tier):
        return True

    pre_p = pre.get("unconditional_pctile")
    post_p = post.get("unconditional_pctile")
    if pre_p is None:
        pre_p = pre.get("pctile_rank_3yr")
    if post_p is None:
        post_p = post.get("pctile_rank_3yr")
    if pre_p is None or post_p is None:
        return False

    pre_p = float(pre_p)
    post_p = float(post_p)
    if pre_p < 80 <= post_p or post_p < 80 <= pre_p:
        return True
    if pre_p > 20 >= post_p or post_p > 20 >= pre_p:
        return True
    return False


def variables_crossed_threshold(pre_readings: dict, post_readings: dict) -> list[str]:
    crossed: list[str] = []
    for vid in VAR_IDS:
        pre = pre_readings.get(vid, {})
        post = post_readings.get(vid, {})
        if crossed_rare_boundary(pre, post):
            crossed.append(vid)
    return crossed


def _combo_letters(fires) -> set[str]:
    return {f.runic_combo for f in fires if f.runic_combo and f.status in (
        "ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3", "WATCH", "CONTESTED"
    )}


def classify_transition_type(metrics: dict[str, Any]) -> str | None:
    cfg = _scheduled_cfg().get("liquidity_shock", {})
    vix_thresh = float(cfg.get("vix_points", 5))
    hy_thresh = float(cfg.get("hy_bps", 30))
    usd_thresh = float(cfg.get("usd_strength_pct", 0.5))

    hy = metrics.get("hy_bps")
    usd = metrics.get("usd_pct")
    vix = metrics.get("vix_pts")
    short = metrics.get("dgs2_bps")
    long_b = metrics.get("long_bps")
    curve = metrics.get("curve_bps")

    if (
        vix is not None
        and hy is not None
        and usd is not None
        and vix >= vix_thresh
        and hy >= hy_thresh
        and usd >= usd_thresh
    ):
        return "LIQUIDITY_SHOCK"

    if hy is not None and usd is not None and short is not None and long_b is not None:
        hy_widened = hy > 0
        hy_compressed = hy < 0
        usd_weakened = usd < 0
        usd_strengthened = usd > 0
        abs_short = abs(short)
        abs_long = abs(long_b)

        if hy_widened and usd_weakened and abs_long > abs_short:
            return "FISCAL_DOMINANCE_FEAR"
        if hy_compressed and usd_strengthened and abs_long < abs_short:
            return "CREDIBILITY_RESTORED"

    if short is not None and long_b is not None and curve is not None:
        abs_short = abs(short)
        abs_long = abs(long_b)
        no_hy_stress = hy is None or hy < hy_thresh

        if abs_short > abs_long and curve < 0 and no_hy_stress:
            return "BEAR_FLATTEN"

        curve_widened = curve > 0
        long_rose_more = abs_long > abs_short
        short_fell_more = short < 0 and long_b is not None and (
            long_b >= 0 or abs(short) > abs(long_b)
        )
        if curve_widened and (long_rose_more or short_fell_more):
            return "BULL_STEEPEN"

    return None


def detect_post_event_transition(as_of: str) -> dict[str, Any]:
    event = get_recent_event_in_window(as_of)
    if not event:
        return dict(INACTIVE_PAYLOAD)

    anchors = event_window_anchors(event["date"], as_of)
    pre_date = anchors["pre_date"]
    post_date = anchors["post_date"]

    pull_all_series(pre_date)
    pull_all_series(post_date)
    pre_readings = get_readings_as_of(pre_date)
    post_readings = get_readings_as_of(post_date)

    crossed = variables_crossed_threshold(pre_readings, post_readings)
    regime_transition = len(crossed) >= 2

    pre_combos = _combo_letters(detect_named_combos(pre_date, pre_readings))
    post_combos = _combo_letters(detect_named_combos(post_date, post_readings))
    combo_diff = sorted(pre_combos ^ post_combos)
    combos_changed = bool(combo_diff)

    metrics = build_event_metrics(pre_date, post_date)
    transition_type = classify_transition_type(metrics) if regime_transition else None

    return {
        "active": True,
        "regime_transition": regime_transition,
        "transition_type": transition_type,
        "event": {"type": event["type"], "date": event["date"]},
        "hours_since_event": event.get("hours_since_event"),
        "pre_date": pre_date,
        "post_date": post_date,
        "variables_crossed": crossed,
        "combos_changed": combos_changed,
        "combo_diff": combo_diff,
        "metrics": {
            k: round(v, 2) if isinstance(v, float) else v
            for k, v in metrics.items()
            if v is not None
        },
    }
