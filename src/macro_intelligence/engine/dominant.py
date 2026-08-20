"""Resolve dominant signal via PRIORITY dict and hit-rate reasoning."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine import combo_metadata
from src.macro_intelligence.engine.combo_metadata import (
    combo_primary_horizon,
    format_reason_hit_rate,
    format_reason_hit_rate_short,
)


def is_validated_combo(letter: str) -> bool:
    """
    True when the combo has enough matured episodes to outrank on PRIORITY alone.

    Rohit sign-off 2026-08-06: a combo with fewer than `min_matured_episodes` matured
    episodes sits below every validated combo. Episode counts reuse the existing
    combo_hit_rate_stats() path (n_obs_primary vs min_episodes_for_hit_rate), so this
    rule and the briefing's "insufficient episodes" wording can never disagree.
    """
    if not letter:
        return False
    try:
        # Resolved through the module (not a from-import) so the same fixture that
        # patches combo_hit_rate_stats for the reason text also drives the ranking.
        stats = combo_metadata.combo_hit_rate_stats(letter)
    except Exception:
        # Never let a stats failure change the ranking — fall back to validated.
        return True
    if not stats.get("show_hit_rate"):
        return False
    return not bool(stats.get("insufficient_episodes"))


def priority_ranking() -> list[dict[str, Any]]:
    """
    The configured priority order after the low-n rule is applied, most dominant first.

    Emitted into the nightly payload so the page can show the order that decides house
    posture — it previously appeared on no tab.
    """
    cfg = load_config().get("dominant", {})
    priority = cfg.get("PRIORITY", {})
    demotion_on = bool(cfg.get("low_n_demotion", True))

    rows: list[dict[str, Any]] = []
    for letter, rank in priority.items():
        validated = is_validated_combo(letter)
        stats = {}
        try:
            stats = combo_metadata.combo_hit_rate_stats(letter) or {}
        except Exception:
            stats = {}
        rows.append({
            "combo": letter,
            "priority": int(rank),
            "validated": validated,
            "matured_episodes": stats.get("n_obs_primary"),
            "min_matured_episodes": stats.get("min_episodes_required")
            or cfg.get("min_matured_episodes", 5),
            "demoted_for_low_n": demotion_on and not validated,
        })

    rows.sort(key=lambda r: (r["demoted_for_low_n"], -r["priority"], r["combo"]))
    for position, row in enumerate(rows, start=1):
        row["position"] = position
    return rows


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
    dominant_cfg = cfg.get("dominant", {})
    priority = dominant_cfg.get("PRIORITY", {})
    demotion_on = bool(dominant_cfg.get("low_n_demotion", True))

    def _rank_key(c: dict[str, Any]) -> tuple[int, int, str]:
        letter = c.get("combo", "")
        # Low-n combos sort last regardless of PRIORITY (Rohit 2026-08-06).
        low_n = 1 if (demotion_on and not is_validated_combo(letter)) else 0
        return (low_n, -int(priority.get(letter, 0)), letter)

    actives = [
        c
        for c in active_combos
        if c.get("status") in ("ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3", "ESCALATION_ALERT")
        and c.get("combo")
    ]

    if not actives:
        return None, "No active named combos.", "NEUTRAL"

    ranked = sorted(actives, key=_rank_key)
    top = ranked[0]
    dominant = top.get("combo")
    reason = _build_reason(dominant, top, ranked[1:3])
    brave = _brave_fearful(dominant, actives, regime)
    return dominant, reason, brave


def _status_verb(status: str | None) -> str:
    mapping = {
        "ACTIVE": "active",
        "PARTIAL": "partial",
        "CONFIRMED": "confirmed (2/3)",
        "CONFIRMED_3_OF_3": "confirmed (3/3)",
        "ESCALATION_ALERT": "confirmed (3/3) with CFTC escalation",
    }
    return mapping.get(status or "", "active")


def _duration_clause(combo: dict[str, Any]) -> str:
    weeks = combo.get("duration_weeks")
    if not isinstance(weeks, int) or weeks < 1:
        return ""
    bucket = combo.get("duration_bucket") or ""
    ep = combo.get("episode_start")
    inner = f"week {weeks}"
    if bucket:
        inner += f", {bucket}"
    if ep:
        inner += f" · started {ep}"
    return f" ({inner})"


def _build_reason(dominant: str, top: dict[str, Any], others: list[dict[str, Any]]) -> str:
    status = _status_verb(top.get("status"))
    duration = _duration_clause(top)
    hr_clause = format_reason_hit_rate(dominant)
    legs = top.get("confirmed_legs")
    leg_txt = f" Legs: {', '.join(legs)}." if legs else ""
    esc_txt = ""
    if top.get("escalation_alert") or top.get("status") == "ESCALATION_ALERT":
        delta = top.get("cftc_pctile_delta")
        if delta is not None:
            esc_txt = f" CFTC FM pctile up {delta:+.1f} pts over lookback — escalation alert."
        else:
            esc_txt = " CFTC FM crowding escalating."
    base = f"Combo {dominant} {status}{duration}. {hr_clause}{leg_txt}{esc_txt}"

    if others:
        alt = others[0].get("combo")
        if alt:
            alt_short = format_reason_hit_rate_short(alt)
            if alt_short:
                base += f" Outranks Combo {alt} ({alt_short}) on configured priority rank."
            else:
                base += f" Outranks Combo {alt} on configured priority rank."
            if not is_validated_combo(alt):
                base += (
                    f" Combo {alt} is ranked below every validated combo"
                    " until it has enough matured episodes."
                )

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
    """Recent combo fires with realized SPX forward returns (requires backfill).

    Every horizon is reported on its own. This used to alias the combo's PRIMARY horizon
    return into `spx_3m_pct`, which is why the page showed 6M identical to 3M in every row
    for a 6M-primary combo (Rohit 2026-08-06). `primary_horizon` still names which column
    the combo is judged on, but it no longer overwrites another horizon's value.
    """
    if not dominant:
        return []
    from src.macro_intelligence.db.connection import get_connection

    primary = combo_primary_horizon(dominant) or "spx_3m"
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT cf.date, fr.{primary} AS primary_ret,
                   fr.spx_1m, fr.spx_3m, fr.spx_6m, fr.spx_9m, fr.spx_12m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = ? AND fr.{primary} IS NOT NULL
            ORDER BY cf.date DESC LIMIT ?
            """,
            (dominant, limit),
        ).fetchall()

    def _pct(value: Any) -> float | None:
        return round(float(value), 2) if value is not None else None

    return [
        {
            "date": r["date"],
            "primary_horizon": primary,
            "primary_pct": _pct(r["primary_ret"]),
            "spx_1m_pct": _pct(r["spx_1m"]),
            "spx_3m_pct": _pct(r["spx_3m"]),
            "spx_6m_pct": _pct(r["spx_6m"]),
            "spx_9m_pct": _pct(r["spx_9m"]),
            "spx_12m_pct": _pct(r["spx_12m"]),
        }
        for r in rows
    ]
