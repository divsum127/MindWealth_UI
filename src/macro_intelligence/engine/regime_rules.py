"""Pure Python regime labels (4 of 5); geo_overlay handled separately."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.data.pull_all import get_readings_as_of
from src.macro_intelligence.engine.fed_cycle import fed_cycle_at_date


def compute_fed_cycle(ffr_change_3m: float | None, walcl_mom: float | None) -> str:
    """Backward-compatible wrapper; prefer fed_cycle_at_date()."""
    label, _ = fed_cycle_at_date("2099-01-01", walcl_mom=walcl_mom)
    if walcl_mom is not None and walcl_mom > 1.0:
        return "QE"
    if walcl_mom is not None and walcl_mom < -0.5:
        return "QT"
    return label


def compute_curve_regime(spread_bps: float | None, steepen_4wk_bps: float | None) -> str:
    if spread_bps is None:
        return "NORMAL"
    if spread_bps < -10:
        return "INVERTED"
    if spread_bps < 30:
        return "FLAT"
    if steepen_4wk_bps and steepen_4wk_bps >= 15:
        return "STEEPENING"
    return "NORMAL"


def compute_val_regime(cape: float | None) -> str:
    if cape is None:
        return "NORMAL"
    if cape >= 32:
        return "EXTREME_CAPE"
    if cape >= 28:
        return "ELEVATED_CAPE"
    if cape <= 16:
        return "CHEAP_CAPE"
    return "NORMAL"


def compute_liquidity(nfci: float | None) -> str:
    if nfci is None:
        return "NEUTRAL"
    if nfci <= -0.5:
        return "GLOBAL_EASY"
    if nfci >= 0.5:
        return "GLOBAL_TIGHT"
    return "NEUTRAL"


def build_python_regime(as_of: str, readings: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    readings = readings or get_readings_as_of(as_of)
    curve = readings.get("CURVE", {})
    spread = curve.get("raw_value")
    meta = {}
    try:
        import json

        meta = json.loads(curve.get("meta_json") or "{}")
    except Exception:
        pass
    nfci = readings.get("NFCI", {}).get("raw_value")
    cape = readings.get("CAPE", {}).get("raw_value")
    walcl = readings.get("WALCL", {}).get("raw_value")

    fed_label, fed_source = fed_cycle_at_date(as_of, walcl_mom=walcl)

    regime = {
        "fed_cycle": fed_label,
        "curve_regime": compute_curve_regime(spread, meta.get("steepen_4wk_bps") or meta.get("steepen_4wk")),
        "val_regime": compute_val_regime(cape),
        "liquidity": compute_liquidity(nfci),
        "fed_cycle_source": fed_source,
        "curve_regime_source": "T10Y2Y",
        "val_regime_source": "CAPE",
        "liquidity_source": "NFCI",
        "geo_overlay": "NEUTRAL",
    }
    return regime
