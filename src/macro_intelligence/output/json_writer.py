"""Write runic_output.json for C++ consumption."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from src.config_paths import SSI_POSITIONING_JSON
from src.macro_intelligence.config import json_output_path
from src.macro_intelligence.data.bls_pull import fetch_ppi_cooling_flag
from src.macro_intelligence.db.connection import get_connection


def read_positioning_data() -> dict[str, Any] | None:
    path = os.environ.get("SSI_POSITIONING_JSON") or str(SSI_POSITIONING_JSON)
    if path and Path(path).exists():
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def read_ssi_multiplier() -> float:
    data = read_positioning_data()
    if not data:
        return 1.0
    try:
        signals = data.get("signals", {})
        long_mult = signals.get("long", {}).get("size_mult")
        if long_mult is not None:
            return float(long_mult)
        return float(data.get("ssi_multiplier", data.get("multiplier", 1.0)))
    except Exception:
        return 1.0


def read_ssi_layer2_status() -> str | None:
    data = read_positioning_data()
    if data:
        return data.get("layer2_status")
    return None


def ssi_confirmed_for_combo_f() -> bool:
    return read_ssi_layer2_status() == "CONFIRMED"


def _combo_c_cancel_state() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT wti_potential_week, active, last_check_date, cancel_date FROM combo_c_cancel WHERE id=1"
        ).fetchone()
    if not row:
        return {"wti_potential_week": 0, "active": False, "cancel_date": None}
    return {
        "wti_potential_week": row["wti_potential_week"],
        "active": bool(row["active"]),
        "last_check_date": row["last_check_date"],
        "cancel_date": row["cancel_date"],
        "cancelled": bool(row["cancel_date"]),
    }


def _pending_cpi_release(as_of: str | None = None) -> bool:
    """True if a CPI release is scheduled this week without finalized actual in DB."""
    from datetime import datetime, timedelta

    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM pending_releases
            WHERE release_type='CPI' AND release_date >= ? AND release_date <= ?
            """,
            (week_start, as_of),
        ).fetchone()
    return bool(row and row["n"] > 0)


def _cftc_status() -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM cftc_positioning ORDER BY date DESC LIMIT 1").fetchone()
    return row["status"] if row else "PENDING_CFTC_CONFIRM"


def write_runic_json(payload: dict[str, Any], path: Path | None = None) -> Path:
    out = path or json_output_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        os.replace(tmp, out)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return out


def build_payload(
    *,
    as_of: str,
    regime: dict[str, str],
    dominant_signal: str | None,
    dominant_reason: str,
    brave_fearful: str,
    active_combos: list[dict[str, Any]],
    watch_combos: list[dict[str, Any]] | list[str],
    persistence_signals: list[dict[str, Any]],
    analog_dates: list[str],
    analog_details: list[dict[str, Any]] | None = None,
    spx_3m_forward_avg: float | None,
    spx_3m_hit_rate: float | None,
    combo_f_active: bool,
    combo_f_weeks_elapsed: int | None,
    narrative: str,
    vix_bypass: bool,
    variables_dashboard: list[dict[str, Any]] | None = None,
    ssi_layer2_status: str | None = None,
    system_recommendation: str | None = None,
    pre_catalyst: dict[str, Any] | None = None,
    post_event_regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pos = read_positioning_data()
    return {
        "date": as_of,
        "regime": regime,
        "dominant_signal": dominant_signal,
        "dominant_reason": dominant_reason,
        "brave_fearful": brave_fearful,
        "active_combos": active_combos,
        "watch_combos": watch_combos,
        "persistence_signals": persistence_signals,
        "ssi_multiplier": read_ssi_multiplier(),
        "ssi_layer2_status": ssi_layer2_status or read_ssi_layer2_status(),
        "ssi_positioning_date": pos.get("date") if pos else None,
        "vix_bypass": vix_bypass,
        "analog_dates": analog_dates,
        "analog_details": analog_details or [],
        "spx_3m_forward_avg": spx_3m_forward_avg,
        "spx_3m_hit_rate": spx_3m_hit_rate,
        "combo_f_active": combo_f_active,
        "combo_f_weeks_elapsed": combo_f_weeks_elapsed,
        "narrative": narrative,
        "variables_dashboard": variables_dashboard or [],
        "ppi_cooling": fetch_ppi_cooling_flag(as_of),
        "combo_c_cancel": _combo_c_cancel_state(),
        "cftc_status": _cftc_status(),
        "pending_cpi_release": _pending_cpi_release(as_of),
        "pre_catalyst": pre_catalyst or {},
        "post_event_regime": post_event_regime or {},
        "system_recommendation": system_recommendation,
    }
