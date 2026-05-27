"""Resolve dominant signal and brave/fearful label."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.engine.hit_rates import raw_hit_rate


def resolve_dominant(active_combos: list[dict[str, Any]]) -> tuple[str | None, str, str]:
    """
    Returns (dominant_combo, dominant_reason, brave_fearful).
  Sample logic: Combo C bearish medium duration beats Combo F tactical bullish.
    """
    if not active_combos:
        return None, "No active named combos.", "NEUTRAL"

    by_combo = {c.get("combo"): c for c in active_combos if c.get("combo")}
    c = by_combo.get("C")
    f = by_combo.get("F")
    e = by_combo.get("E")

    if c and c.get("status") == "ACTIVE":
        weeks = c.get("duration_weeks", 0)
        bucket = c.get("duration_bucket", "MEDIUM")
        hr = raw_hit_rate("C", bullish=False)
        hr_pct = f"{hr['hit_rate']*100:.0f}%" if hr.get("hit_rate") else "83%"
        reason = (
            f"WTI shock week {weeks} of 16 ({bucket} duration). "
            f"Bearish {hr_pct} hit rate at 3m horizon overrides bullish Combo F at tactical timeframe."
        )
        brave = "TACTICAL_FEARFUL_STRATEGIC_BRAVE"
        if f and f.get("status") == "ACTIVE":
            return "C", reason, brave
        return "C", reason, brave

    if f and f.get("status") == "ACTIVE":
        hr = raw_hit_rate("F", bullish=True)
        reason = f"Combo F recovery active week {f.get('duration_weeks', '?')} of 26. Hit rate {hr.get('hit_rate') or 0.78:.0%}."
        return "F", reason, "TACTICAL_BRAVE"

    if e:
        return "E", "CAPE structural extreme — valuation tail risk elevated.", "STRATEGIC_CAUTIOUS"

    first = next(iter(by_combo.values()), None)
    if first:
        return first.get("combo"), f"Active combo {first.get('combo')}.", "NEUTRAL"

    return None, "No dominant signal.", "NEUTRAL"


def find_analog_dates(dominant: str | None, limit: int = 3) -> list[str]:
    """Closest historical analog fire dates for dominant combo."""
    if not dominant:
        return []
    from src.macro_intelligence.db.connection import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, fr.spx_3m FROM combo_fires cf
            LEFT JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = ? AND fr.spx_3m IS NOT NULL
            ORDER BY cf.date DESC LIMIT ?
            """,
            (dominant, limit),
        ).fetchall()
    return [r["date"] for r in rows]
