"""VIX regime multiplier bypass — CRITICAL RULE (Addendum A6)."""

from __future__ import annotations

# CRITICAL RULE: VIX_REGIME_BYPASS (Addendum A6)
# vix_bypass is set ONLY when Combo B (Maximum Capitulation) is confirmed ACTIVE.
# When true, C++ ignores the SSI size multiplier entirely (size_mult forced to 1.0).
# Historical basis: Oct 13, 2022 — VIX 33.6 would have triggered 0.75x
# multiplier but Combo B fired simultaneously.

VIX_REGIME_BYPASS_COMBOS = ("B",)

VIX_BYPASS_BANNER = (
    "VIX REGIME MULTIPLIER BYPASSED - Combo B active. Full size in effect."
)


def combo_b_is_active(active_combos: list[dict]) -> bool:
    """True when Combo B is confirmed ACTIVE in active_combos."""
    for c in active_combos:
        if not isinstance(c, dict):
            continue
        if c.get("combo") == "B" and c.get("status") == "ACTIVE":
            return True
    return False


def compute_vix_bypass(active_combos: list[dict], ssi_confirmed_f: bool = False) -> bool:
    """Return True only when Combo B is ACTIVE (A6). Combo F+SSI does not bypass."""
    _ = ssi_confirmed_f  # retained for call-site compatibility; ignored per A6
    return combo_b_is_active(active_combos)


def assert_vix_bypass_consistency(active_combos: list[dict], vix_bypass: bool) -> None:
    """Raise if vix_bypass is true without Combo B ACTIVE."""
    combo_b_active = combo_b_is_active(active_combos)
    if vix_bypass and not combo_b_active:
        raise ValueError(
            "vix_bypass=True requires Combo B status=='ACTIVE'; "
            f"active_combos={active_combos!r}"
        )
