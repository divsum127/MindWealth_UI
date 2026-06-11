"""Tests for regime v2 experiment helpers."""

from src.macro_intelligence.analysis.regime_experiments.metrics import hit_rate, summarize_returns
from src.macro_intelligence.engine.regime_v2_shadow import collapse_fed_cycle_v2


def test_collapse_fed_cycle_v2():
    assert collapse_fed_cycle_v2("HIKING_LATE") == "TIGHTENING"
    assert collapse_fed_cycle_v2("CUTTING_EARLY") == "PIVOTING"
    assert collapse_fed_cycle_v2("QE") == "EASY"


def test_summarize_returns():
    s = summarize_returns([1.0, -0.5, 2.0])
    assert s["n"] == 3
    assert s["hit_rate"] == 2 / 3
