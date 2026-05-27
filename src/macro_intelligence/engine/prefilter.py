"""Pre-filter gate for unnamed combos before Claude."""

from __future__ import annotations

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine.hit_rates import raw_hit_rate
from src.macro_intelligence.models import GateFlag


def apply_prefilter(runic_combo: str | None, var_signature: str) -> GateFlag:
    cfg = load_config()
    pf = cfg.get("prefilter", {})
    min_fires = pf.get("min_historical_fires", 3)
    min_hr = pf.get("min_hit_rate", 0.60)

    if runic_combo in ("A", "B", "C", "D", "E", "F", "G"):
        return GateFlag.SIGNAL

    stats = raw_hit_rate(var_signature, horizon="spx_3m") if len(var_signature) == 1 else raw_hit_rate(
        runic_combo or "?", horizon="spx_3m"
    )
    # For unnamed combos keyed by var set — use combo history from DB via runic_combo None
    if runic_combo:
        stats = raw_hit_rate(runic_combo)
    else:
        stats = {"n_obs": 0, "hit_rate": None}

    if stats["n_obs"] < min_fires:
        return GateFlag.BELOW_GATE
    if stats["hit_rate"] is None or stats["hit_rate"] < min_hr:
        return GateFlag.BELOW_GATE
    return GateFlag.SIGNAL


def is_named_combo_candidate(runic_combo: str | None) -> bool:
    if runic_combo:
        return False
    cfg = load_config()
    pf = cfg.get("prefilter", {})
    stats = raw_hit_rate("?")  # placeholder — monthly review uses dedicated query
    return stats.get("n_obs", 0) >= pf.get("candidate_named_min_fires", 3) and (
        stats.get("hit_rate") or 0
    ) >= pf.get("candidate_named_min_hit_rate", 0.75)
