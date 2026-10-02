"""Combo C cancellation: 4 Fridays WTI < +5% and CPI not hot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.db.connection import get_connection


def _is_friday(date_str: str) -> bool:
    return pd.Timestamp(date_str).dayofweek == 4


def _governing_cpi_print(as_of: str) -> dict[str, Any] | None:
    """Most recent confirmed CPI print on or before as_of (regardless of publication week)."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT release_date, actual, consensus, surprise_pp
            FROM pending_releases
            WHERE release_type='CPI' AND release_date <= ?
              AND actual IS NOT NULL AND consensus IS NOT NULL
            ORDER BY release_date DESC LIMIT 1
            """,
            (as_of,),
        ).fetchone()
    if not row:
        return None
    return {
        "release_date": row["release_date"],
        "actual": float(row["actual"]),
        "consensus": float(row["consensus"]),
        "surprise_pp": row["surprise_pp"],
    }


def cpi_leg_passes(as_of: str) -> tuple[bool, dict[str, Any] | None]:
    """
    CPI cancel leg: PASSES if governing print shows actual <= consensus.
    BLOCKED if actual > consensus. No PPI substitute.
    """
    gov = _governing_cpi_print(as_of)
    if not gov:
        return True, None
    return gov["actual"] <= gov["consensus"], gov


def run_combo_c_cancel_check(as_of: str, wti_4wk_pct: float | None, combo_c_active: bool) -> dict[str, Any]:
    cfg = load_config().get("combo_c_cancel", {})
    wti_max = cfg.get("wti_4wk_max_pct", 5.0)
    need_weeks = cfg.get("consecutive_fridays", 4)

    with get_connection() as conn:
        row = conn.execute(
            """SELECT wti_potential_week, last_check_date, cancel_date, active, entry_date
               FROM combo_c_cancel WHERE id=1"""
        ).fetchone()
    week = int(row["wti_potential_week"]) if row else 0
    last_check = row["last_check_date"] if row else None
    cancel_date = row["cancel_date"] if row else None
    entry_date = row["entry_date"] if row else None

    # A detector-confirmed active signal is the only route into a new episode.
    # This also makes direct callers/tests record the invariant explicitly.
    if combo_c_active and not entry_date:
        entry_date = as_of
        cancel_date = None
        week = 0
        last_check = None
        with get_connection() as conn:
            conn.execute(
                """UPDATE combo_c_cancel
                   SET active=1, entry_date=?, cancel_date=NULL, wti_potential_week=0,
                       last_check_date=NULL, updated_at=datetime('now') WHERE id=1""",
                (as_of,),
            )

    if cancel_date:
        return {
            "wti_potential_week": week,
            "cancelled": True,
            "active": False,
            "cancel_date": cancel_date,
        }

    if not combo_c_active:
        if not (row and row["active"] and entry_date):
            with get_connection() as conn:
                conn.execute(
                    """UPDATE combo_c_cancel
                       SET wti_potential_week=0, active=0, entry_date=NULL,
                           cancel_date=NULL, last_check_date=?, updated_at=datetime('now')
                       WHERE id=1""",
                    (as_of,),
                )
            return {"wti_potential_week": 0, "cancelled": False, "active": False, "cancel_date": None}
        # Fall through — DB says active=1; advance cancel counter on Fridays.

    if not _is_friday(as_of):
        return {"wti_potential_week": week, "cancelled": False, "active": True, "cancel_date": None}

    if last_check == as_of:
        return {"wti_potential_week": week, "cancelled": False, "active": True, "cancel_date": None}

    wti_ok = wti_4wk_pct is not None and wti_4wk_pct < wti_max
    cpi_ok, cpi_gov = cpi_leg_passes(as_of)

    if wti_ok and cpi_ok:
        week = min(week + 1, need_weeks)
    else:
        week = 0

    cancelled = week >= need_weeks
    new_cancel_date = as_of if cancelled else None
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE combo_c_cancel SET wti_potential_week=?, last_check_date=?, cpi_leg_passed=?,
            active=?, entry_date=CASE WHEN ? THEN NULL ELSE entry_date END,
            cancel_date=COALESCE(?, cancel_date), updated_at=datetime('now') WHERE id=1
            """,
            (week, as_of, 1 if cpi_ok else 0, 0 if cancelled else 1,
             1 if cancelled else 0, new_cancel_date),
        )

    return {
        "wti_potential_week": week,
        "cancelled": cancelled,
        "active": not cancelled,
        "wti_leg_ok": wti_ok,
        "cpi_leg_ok": cpi_ok,
        "governing_cpi": cpi_gov,
        "cancel_date": new_cancel_date or cancel_date,
    }
