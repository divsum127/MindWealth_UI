"""Resolve dominant signal via PRIORITY dict and hit-rate reasoning."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine.combo_metadata import (
    combo_bullish,
    combo_hit_rate_stats,
    combo_primary_horizon,
    horizon_display_label,
)
from src.macro_intelligence.engine.hit_rates import raw_hit_rate


def determine_dominant_combo(
    active_combos: list[dict[str, Any]],
    regime: dict[str, str] | None = None,
) -> tuple[str | None, str, str]:
    """Returns (dominant_combo, dominant_reason, brave_fearful)."""
    return resolve_dominant(active_combos, regime)


def resolve_dominant(
    active_combos: list[dict[str, Any]],
    regime: dict[str, str] | None = None,
) -> tuple[str | None, str, str]:
    if not active_combos:
        return None, "No active named combos.", "NEUTRAL"

    cfg = load_config()
    priority = cfg.get("dominant", {}).get("PRIORITY", {})
    actives = [
        c
        for c in active_combos
        if c.get("status") in ("ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3")
        and c.get("combo")
    ]

    if not actives:
        return None, "No active named combos.", "NEUTRAL"

    def _score(c: dict[str, Any]) -> int:
        return int(priority.get(c.get("combo", ""), 0))

    ranked = sorted(actives, key=_score, reverse=True)
    top = ranked[0]
    dominant = top.get("combo")
    reason = _build_reason(dominant, top, ranked[1:3])
    brave = _brave_fearful(dominant, actives, regime)
    return dominant, reason, brave


def _build_reason(dominant: str, top: dict[str, Any], others: list[dict[str, Any]]) -> str:
    bullish = combo_bullish(dominant)
    if bullish is None:
        bullish = dominant in ("B", "F")
    primary = combo_primary_horizon(dominant) or "spx_3m"
    hr = raw_hit_rate(dominant, horizon=primary, bullish=bool(bullish))
    hr_pct = f"{(hr.get('hit_rate') or 0) * 100:.0f}%"
    h_label = horizon_display_label(primary)
    weeks = top.get("duration_weeks", "?")
    bucket = top.get("duration_bucket", "")
    ep = top.get("episode_start")
    dur = f"week {weeks}"
    if bucket:
        dur += f", {bucket}"
    if ep:
        dur += f" (started {ep})"
    legs = top.get("confirmed_legs")
    leg_txt = f" Legs: {', '.join(legs)}." if legs else ""
    base = f"Combo {dominant} active ({dur}). {hr_pct} {h_label} hit rate.{leg_txt}"
    if others:
        alt = others[0].get("combo")
        alt_bull = combo_bullish(alt)
        if alt_bull is None:
            alt_bull = alt in ("B", "F")
        alt_primary = combo_primary_horizon(alt) or "spx_3m"
        alt_hr = raw_hit_rate(alt, horizon=alt_primary, bullish=bool(alt_bull))
        alt_pct = f"{(alt_hr.get('hit_rate') or 0) * 100:.0f}%"
        alt_label = horizon_display_label(alt_primary)
        base += f" Outranks Combo {alt} ({alt_pct} {alt_label}) on PRIORITY and horizon fit."
    if dominant == "C":
        base += " Bearish medium-duration energy shock dominates tactical bullish recovery signals."
    return base


def _brave_fearful(dominant: str, actives: list[dict[str, Any]], regime: dict[str, str] | None) -> str:
    has_f = any(c.get("combo") == "F" and c.get("status") == "ACTIVE" for c in actives)
    has_c = dominant == "C"
    if has_c and has_f:
        return "TACTICAL_TIGHT_MONEY_STRATEGIC_EASY_MONEY"
    if dominant == "F":
        return "TACTICAL_EASY_MONEY"
    if dominant == "E":
        return "STRATEGIC_CAUTIOUS"
    if dominant == "B":
        return "TACTICAL_TIGHT_MONEY"
    return "NEUTRAL"


def find_analog_dates(dominant: str | None, limit: int = 3) -> list[str]:
    return [a["date"] for a in find_analog_details(dominant, limit=limit)]


def find_analog_details(dominant: str | None, limit: int = 3) -> list[dict[str, Any]]:
    """Recent combo fires with realized SPX forward returns (requires backfill)."""
    if not dominant:
        return []
    from src.macro_intelligence.db.connection import get_connection

    primary = combo_primary_horizon(dominant) or "spx_3m"
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT cf.date, fr.{primary} AS primary_ret, fr.spx_1m, fr.spx_6m, fr.spx_12m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = ? AND fr.{primary} IS NOT NULL
            ORDER BY cf.date DESC LIMIT ?
            """,
            (dominant, limit),
        ).fetchall()
    return [
        {
            "date": r["date"],
            "spx_3m_pct": round(float(r["primary_ret"]), 2),
            "primary_horizon": primary,
            "spx_1m_pct": round(float(r["spx_1m"]), 2) if r["spx_1m"] is not None else None,
            "spx_6m_pct": round(float(r["spx_6m"]), 2) if r["spx_6m"] is not None else None,
            "spx_12m_pct": round(float(r["spx_12m"]), 2) if r["spx_12m"] is not None else None,
        }
        for r in rows
    ]
