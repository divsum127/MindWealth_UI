"""Tests for Part H combo discovery pipeline."""

from __future__ import annotations

import pytest

from src.macro_intelligence.analysis.combo_discovery_pipeline import (
    ComboResult,
    FireRecord,
    _directionality_check,
    _evaluate_signature,
    _hit_rate,
    combo_signature,
    enumerate_all_signatures,
)
from src.macro_intelligence.engine.combo_detector import VAR_IDS


def test_enumerate_exactly_298_signatures():
    sigs = enumerate_all_signatures()
    assert len(sigs) == 298
    singles = sum(1 for s in sigs if len(s) == 1)
    pairs = sum(1 for s in sigs if len(s) == 2)
    triples = sum(1 for s in sigs if len(s) == 3)
    assert singles == 12
    assert pairs == 66
    assert triples == 220


def test_combo_signature_sorted():
    assert combo_signature(("VIX", "HY")) == "HY+VIX"


def test_hit_rate_bullish_bearish():
    assert _hit_rate([1.0, -0.5, 2.0], bullish=True) == pytest.approx(2 / 3)
    assert _hit_rate([1.0, -0.5, -2.0], bullish=False) == pytest.approx(2 / 3)


def _fire(date: str, ret: float, fed: str = "QE", curve: str = "NORMAL") -> FireRecord:
    return FireRecord(
        combo_id=1,
        date=date,
        var_ids=("VIX", "HY"),
        directions=["HIGH", "WIDE"],
        returns={"spx_3m": ret, "spx_1m": ret, "spx_6m": ret, "spx_9m": ret, "spx_12m": ret},
        regime={"fed_cycle": fed, "curve_regime": curve, "val_regime": "FAIR", "geo_overlay": "NEUTRAL", "liquidity": "GLOBAL_EASY"},
    )


def test_surface_gate_filters_low_n():
    cfg = {
        "primary_horizon": "spx_3m",
        "surface_min_fires": 3,
        "surface_min_hit_rate": 0.60,
        "beta_min_hit_rate": 0.55,
        "directionality_min_dims": 2,
        "directionality_min_hit_rate": 0.50,
        "hostile_fed_cycles": ["HIKING_EARLY"],
        "hostile_curve_regimes": ["INVERTED"],
    }
    fires = [_fire("2020-01-03", 5.0), _fire("2020-01-10", 3.0)]
    result = _evaluate_signature(("VIX", "HY"), fires, fires, cfg)
    assert result.gate_stage == "below_surface"
    assert not result.surfaced


def test_directionality_requires_two_dims():
    cfg = {"directionality_min_dims": 2, "directionality_min_hit_rate": 0.50}
    fires = [
        _fire("2020-01-03", 5.0, fed="QE", curve="NORMAL"),
        _fire("2020-02-07", 4.0, fed="QE", curve="STEEPENING"),
        _fire("2020-03-06", -2.0, fed="HIKING_EARLY", curve="INVERTED"),
        _fire("2020-04-03", -3.0, fed="HIKING_EARLY", curve="INVERTED"),
    ]
    ok, count, _ = _directionality_check(fires, "spx_3m", bullish=True, cfg=cfg)
    assert count >= 1


def test_no_threshold_mutation_in_cfg_keys():
    """Pipeline reads combo_discovery block; variable rare tiers untouched."""
    from src.macro_intelligence.config import load_config

    cfg = load_config()
    assert "combo_discovery" in cfg
    assert "variables" in cfg
    assert cfg["combo_discovery"]["surface_min_hit_rate"] == 0.60
    assert len(VAR_IDS) == 12
