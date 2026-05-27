"""Write runic_output.json for C++ consumption."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from src.macro_intelligence.config import json_output_path


def read_ssi_multiplier() -> float:
    path = os.environ.get("SSI_POSITIONING_JSON")
    if path and Path(path).exists():
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return float(data.get("ssi_multiplier", data.get("multiplier", 1.0)))
        except Exception:
            pass
    return 1.0


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
    watch_combos: list[str],
    persistence_signals: list[dict[str, Any]],
    analog_dates: list[str],
    spx_3m_forward_avg: float | None,
    spx_3m_hit_rate: float | None,
    combo_f_active: bool,
    combo_f_weeks_elapsed: int | None,
    narrative: str,
    vix_bypass: bool,
    variables_dashboard: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
        "vix_bypass": vix_bypass,
        "analog_dates": analog_dates,
        "spx_3m_forward_avg": spx_3m_forward_avg,
        "spx_3m_hit_rate": spx_3m_hit_rate,
        "combo_f_active": combo_f_active,
        "combo_f_weeks_elapsed": combo_f_weeks_elapsed,
        "narrative": narrative,
        "variables_dashboard": variables_dashboard or [],
    }
