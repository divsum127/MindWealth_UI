"""VIX regime multiplier bypass — CRITICAL RULE."""

from __future__ import annotations

# CRITICAL RULE: VIX_REGIME_BYPASS
# When runic_combo = 'B' (Maximum Capitulation) is confirmed active,
# the VIX regime size multiplier is BYPASSED. Do NOT reduce position
# size during a confirmed Combo B.
# Historical basis: Oct 13, 2022 — VIX 33.6 would have triggered 0.75x
# multiplier but Combo B fired simultaneously.
# Same bypass applies to Combo F when SSI confirms (>=2 of 4 signals).

VIX_REGIME_BYPASS_COMBOS = ("B",)


def compute_vix_bypass(active_combos: list[dict], ssi_confirmed_f: bool = False) -> bool:
    for c in active_combos:
        combo = c.get("combo") if isinstance(c, dict) else c
        status = c.get("status", "ACTIVE") if isinstance(c, dict) else "ACTIVE"
        if combo in VIX_REGIME_BYPASS_COMBOS and status == "ACTIVE":
            return True
    if ssi_confirmed_f:
        for c in active_combos:
            if isinstance(c, dict) and c.get("combo") == "F" and c.get("status") == "ACTIVE":
                return True
    return False
