"""Sweep named combo thresholds vs forward returns in runic.db."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.combo_detector import evaluate_combo_b_at_date


def sweep_combo_b_vix_thresholds(
    vix_levels: list[float] | None = None,
    hy_bps: float = 400.0,
    cftc_pctile: float = 15.0,
) -> list[dict[str, Any]]:
    """Evaluate Combo B gate across VIX thresholds on historical combo_fires dates."""
    vix_levels = vix_levels or [20, 22, 25, 27, 30, 35]
    rows: list[dict[str, Any]] = []
    with get_connection() as conn:
        fires = conn.execute(
            "SELECT date FROM combo_fires WHERE runic_combo='B' ORDER BY date"
        ).fetchall()
    for vix_min in vix_levels:
        count = sum(1 for _ in fires if evaluate_combo_b_at_date("x", vix_min + 1, hy_bps, cftc_pctile))
        rows.append({"param": "vix_min", "value": vix_min, "would_fire_on_b_dates": count})
    return rows


def hit_rate_for_combo(runic_combo: str, bullish: bool = True) -> dict[str, Any]:
    col = "spx_3m"
    with get_connection() as conn:
        data = conn.execute(
            f"""
            SELECT fr.{col} AS ret
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = ? AND fr.{col} IS NOT NULL
            """,
            (runic_combo,),
        ).fetchall()
    if not data:
        return {"combo": runic_combo, "n_obs": 0, "hit_rate": None, "avg_return": None}
    rets = [float(r["ret"]) for r in data]
    if bullish:
        hits = sum(1 for x in rets if x > 0)
    else:
        hits = sum(1 for x in rets if x < 0)
    return {
        "combo": runic_combo,
        "n_obs": len(rets),
        "hit_rate": round(hits / len(rets), 4),
        "avg_return": round(sum(rets) / len(rets), 4),
    }


def suggest_threshold_changes() -> list[dict[str, Any]]:
    """Produce suggestions for CONFIG thresholds from DB hit rates."""
    cfg = load_config()
    suggestions: list[dict[str, Any]] = []

    b_hr = hit_rate_for_combo("B", bullish=True)
    if b_hr["n_obs"] >= 3 and b_hr["hit_rate"] is not None and b_hr["hit_rate"] < 0.6:
        suggestions.append(
            {
                "combo": "B",
                "issue": "low_hit_rate",
                "current": cfg.get("named_combos", {}).get("B", {}),
                "stats": b_hr,
                "suggestion": "Consider raising vix_min or hy_bps_min after review",
            }
        )

    f_hr = hit_rate_for_combo("F", bullish=True)
    if f_hr["n_obs"] >= 3 and f_hr["hit_rate"] is not None and f_hr["hit_rate"] < 0.6:
        suggestions.append(
            {
                "combo": "F",
                "issue": "low_hit_rate",
                "current": cfg.get("named_combos", {}).get("F", {}),
                "stats": f_hr,
                "suggestion": "Review spx_50wma_reclaim_weekly_pct or cftc_max_pctile",
            }
        )

    for vix in [22, 25, 28, 30]:
        suggestions.append(
            {
                "combo": "B",
                "param_sweep": "vix_min",
                "value": vix,
                "note": "Run full backfill before trusting counts",
            }
        )

    return suggestions
