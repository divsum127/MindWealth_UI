"""Tests for post-event regime transition classifier."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.post_event_transition import (
    classify_transition_type,
    crossed_rare_boundary,
    variables_crossed_threshold,
)


class TestPostEventTransition(unittest.TestCase):
    def test_crossed_rare_boundary_tier(self) -> None:
        pre = {"signal_tier": "NORMAL", "unconditional_pctile": 50}
        post = {"signal_tier": "RARE", "unconditional_pctile": 82}
        self.assertTrue(crossed_rare_boundary(pre, post))

    def test_crossed_rare_boundary_pctile(self) -> None:
        pre = {"signal_tier": "NORMAL", "unconditional_pctile": 75}
        post = {"signal_tier": "NORMAL", "unconditional_pctile": 85}
        self.assertTrue(crossed_rare_boundary(pre, post))

    def test_no_cross(self) -> None:
        pre = {"signal_tier": "NORMAL", "unconditional_pctile": 50}
        post = {"signal_tier": "NORMAL", "unconditional_pctile": 55}
        self.assertFalse(crossed_rare_boundary(pre, post))

    def test_variables_crossed_threshold(self) -> None:
        pre = {
            "HY": {"signal_tier": "NORMAL", "unconditional_pctile": 70},
            "CNH": {"signal_tier": "NORMAL", "unconditional_pctile": 50},
            "VIX": {"signal_tier": "NORMAL", "unconditional_pctile": 40},
        }
        post = {
            "HY": {"signal_tier": "RARE", "unconditional_pctile": 85},
            "CNH": {"signal_tier": "RARE", "unconditional_pctile": 82},
            "VIX": {"signal_tier": "NORMAL", "unconditional_pctile": 45},
        }
        crossed = variables_crossed_threshold(pre, post)
        self.assertEqual(set(crossed), {"HY", "CNH"})

    def test_liquidity_shock_priority(self) -> None:
        t = classify_transition_type(
            {"vix_pts": 6, "hy_bps": 35, "usd_pct": 0.6, "dgs2_bps": 10, "long_bps": 5}
        )
        self.assertEqual(t, "LIQUIDITY_SHOCK")

    def test_credibility_restored(self) -> None:
        t = classify_transition_type(
            {"hy_bps": -12, "usd_pct": 0.8, "dgs2_bps": 8, "long_bps": 2, "curve_bps": -6}
        )
        self.assertEqual(t, "CREDIBILITY_RESTORED")

    def test_fiscal_dominance_fear(self) -> None:
        t = classify_transition_type(
            {"hy_bps": 20, "usd_pct": -0.5, "dgs2_bps": 5, "long_bps": 15, "curve_bps": 10}
        )
        self.assertEqual(t, "FISCAL_DOMINANCE_FEAR")

    def test_bear_flatten(self) -> None:
        t = classify_transition_type(
            {"hy_bps": 10, "dgs2_bps": 12, "long_bps": 3, "curve_bps": -8}
        )
        self.assertEqual(t, "BEAR_FLATTEN")

    def test_bull_steepen(self) -> None:
        t = classify_transition_type(
            {"hy_bps": 5, "dgs2_bps": 2, "long_bps": 10, "curve_bps": 8}
        )
        self.assertEqual(t, "BULL_STEEPEN")

    def test_warsh_june_17_credibility_pattern(self) -> None:
        """June 17 2026 FOMC — hawkish Fed, short rates up, long flat, credit fine."""
        t = classify_transition_type(
            {
                "hy_bps": -8,
                "usd_pct": 0.4,
                "dgs2_bps": 6,
                "long_bps": 1,
                "curve_bps": -5,
                "vix_pts": 0.5,
            }
        )
        self.assertEqual(t, "CREDIBILITY_RESTORED")


if __name__ == "__main__":
    unittest.main()
