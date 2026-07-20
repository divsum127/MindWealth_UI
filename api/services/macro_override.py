"""Macro regime override flags for portfolio and AI Analyst panels."""

from __future__ import annotations

from typing import Any


def compute_macro_override(runic: dict[str, Any]) -> dict[str, Any]:
    """CAPE extreme + non-neutral geo overlay → manual ceiling review warning."""
    regime = runic.get("regime", {})
    reasons: list[str] = []
    val = (regime.get("val_regime") or regime.get("valuation") or "").upper()
    if "EXTREME" in val:
        cape_val = None
        for v in runic.get("variables_dashboard", []):
            if isinstance(v, dict) and v.get("variable") == "CAPE":
                cape_val = v.get("current")
        reasons.append(f"Valuation extreme: CAPE {cape_val:.1f}×" if cape_val else "Valuation extreme")
    geo = (regime.get("geo_overlay") or regime.get("geo") or "").upper()
    if geo and geo != "NEUTRAL":
        reasons.append(f"Geopolitical: {geo.replace('_', ' ').title()}")
    return {"active": bool(reasons), "reasons": reasons}
