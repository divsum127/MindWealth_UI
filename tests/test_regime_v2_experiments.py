"""Tests for regime v2 experiment helpers."""

from src.macro_intelligence.analysis.regime_experiments.metrics import hit_rate, slice_by_regime, summarize_returns
from src.macro_intelligence.engine.regime_v2_shadow import (
    collapse_fed_cycle_v2,
    collapse_liquidity_v2_analytics,
    fed_cycle_v2_analytics,
    regime_value_for_analytics,
)


def test_collapse_fed_cycle_v2():
    assert collapse_fed_cycle_v2("HIKING_LATE") == "TIGHTENING"
    assert collapse_fed_cycle_v2("CUTTING_EARLY") == "PIVOTING"
    assert collapse_fed_cycle_v2("QE") == "EASY"


def test_fed_cycle_v2_analytics_merges_pivoting():
    assert fed_cycle_v2_analytics("PIVOTING") == "EASING"
    assert fed_cycle_v2_analytics("TIGHTENING") == "TIGHTENING"


def test_collapse_liquidity_v2_analytics():
    assert collapse_liquidity_v2_analytics("EASY_IMPROVING") == "EASY_IMPROVING"
    assert collapse_liquidity_v2_analytics("NEUTRAL_FLAT") == "EASY_TIGHTENING"
    assert collapse_liquidity_v2_analytics("NEUTRAL_IMPROVING") == "EASY_IMPROVING"
    assert collapse_liquidity_v2_analytics("NEUTRAL_TIGHTENING", nfci=0.5) == "TIGHT_TIGHTENING"
    assert collapse_liquidity_v2_analytics("EASY_FLAT", walcl_trend_4wk=1.0) == "EASY_IMPROVING"


def test_slice_by_regime_analytics_collapse():
    rows = [
        {"returns": {"spx_3m": 1.0}, "regime": {"fed_cycle_v2": "PIVOTING"}},
        {"returns": {"spx_3m": 2.0}, "regime": {"fed_cycle_v2": "EASING"}},
    ]
    sliced = slice_by_regime(rows, "fed_cycle_v2", "spx_3m", bullish=True)
    assert set(sliced.keys()) == {"EASING"}
    assert sliced["EASING"]["n"] == 2


def test_regime_value_for_analytics_liquidity():
    reg = {"liquidity_v2": "NEUTRAL_FLAT"}
    assert regime_value_for_analytics(reg, "liquidity_v2") == "EASY_TIGHTENING"


def test_summarize_returns():
    s = summarize_returns([1.0, -0.5, 2.0])
    assert s["n"] == 3
    assert s["hit_rate"] == 2 / 3
