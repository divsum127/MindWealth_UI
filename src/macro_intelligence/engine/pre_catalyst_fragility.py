"""Pre-catalyst fragility score — near-threshold variable count before macro events."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.macro_calendar import get_upcoming_event
from src.macro_intelligence.engine.combo_detector import VAR_IDS

FRAGILITY_LABEL = "HIGH — REGIME SENSITIVE TO CATALYST"


def _scheduled_cfg() -> dict[str, Any]:
    return load_config().get("scheduled_events", {})


def _near_threshold_bands() -> tuple[tuple[float, float], tuple[float, float]]:
    cfg = _scheduled_cfg()
    high = cfg.get("near_threshold_pctile", [60, 79])
    low = cfg.get("near_threshold_low_pctile", [21, 40])
    return (float(high[0]), float(high[1])), (float(low[0]), float(low[1]))


def is_near_threshold(pctile: float | None) -> bool:
    if pctile is None:
        return False
    (h_lo, h_hi), (l_lo, l_hi) = _near_threshold_bands()
    return (h_lo <= pctile <= h_hi) or (l_lo <= pctile <= l_hi)


def count_near_threshold(readings: dict[str, dict[str, Any]]) -> tuple[int, list[str]]:
    near: list[str] = []
    for vid in VAR_IDS:
        row = readings.get(vid, {})
        pctile = row.get("unconditional_pctile")
        if pctile is None:
            pctile = row.get("pctile_rank_3yr")
        if is_near_threshold(pctile):
            near.append(vid)
    return len(near), near


def compute_pre_catalyst_fragility(
    as_of: str,
    readings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cfg = _scheduled_cfg()
    min_vars = int(cfg.get("fragility_min_vars", 4))
    upcoming = get_upcoming_event(as_of)
    count, vars_near = count_near_threshold(readings)

    inactive = {
        "active": False,
        "upcoming_event": None,
        "days_to_event": None,
        "near_threshold_count": count,
        "near_threshold_vars": vars_near,
        "fragility_score": None,
    }
    if not upcoming:
        return inactive

    score = FRAGILITY_LABEL if count >= min_vars else None
    return {
        "active": True,
        "upcoming_event": {"type": upcoming["type"], "date": upcoming["date"]},
        "days_to_event": upcoming.get("days_to_event"),
        "near_threshold_count": count,
        "near_threshold_vars": vars_near,
        "fragility_score": score,
    }
