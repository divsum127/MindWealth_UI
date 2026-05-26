"""Tests for deep research gate (flagged IFT/CEN block-sale scenario)."""

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))


def _load_gate():
    spec = importlib.util.spec_from_file_location(
        "deep_research_gate",
        _ROOT / "chatbot" / "agents" / "deep_research_gate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_flagged_block_sale_query_triggers_auto_detect():
    gate = _load_gate()
    user_msg = (
        "so why havent u done this - look at block sales, what happened after "
        "Specific NZ Precedents: Trustpower sale (2022) Z Energy stake reduction "
        "Genesis Energy placements Meridian Energy selldowns "
        "1 month and 3 months and 6 months down the line"
    )
    assert gate.should_deep_research(
        user_msg,
        enable_deep_research_config=True,
        deep_research_enabled=False,
    )


def test_simple_signal_query_does_not_auto_trigger():
    gate = _load_gate()
    assert not gate.should_deep_research(
        "show TRENDPULSE entry signals for AAPL last week",
        enable_deep_research_config=True,
        deep_research_enabled=False,
    )


def test_toggle_forces_deep_research():
    gate = _load_gate()
    assert gate.should_deep_research(
        "show TRENDPULSE entry signals for AAPL",
        enable_deep_research_config=True,
        deep_research_enabled=True,
    )


if __name__ == "__main__":
    test_flagged_block_sale_query_triggers_auto_detect()
    test_simple_signal_query_does_not_auto_trigger()
    test_toggle_forces_deep_research()
    print("all tests passed")
