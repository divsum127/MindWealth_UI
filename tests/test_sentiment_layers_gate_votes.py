"""Regression: sentiment/layers must expose all six Layer-2 gate votes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services.reports_service import _ensure_layer2_gate_votes


class TestSentimentLayersGateVotes(unittest.TestCase):
    def test_backfills_gate_votes_from_layer2_components(self) -> None:
        inputs = {
            "layer2_votes": [
                {"input": "hyg_lqd", "raw": 0.75, "vote": True, "signal": "risk_on"},
                {"input": "vix_ratio", "raw": 1.09, "vote": True, "signal": "stress"},
            ],
            "layer2_components": {
                "mcclellan": {"raw": -12.0, "norm": -0.6},
                "nh_nl_ratio": {"raw": 0.73, "norm": -0.1},
                "hyg_lqd": {"raw": 0.75, "norm": 1.2},
                "skew": {"raw": 150.0, "norm": -0.8},
                "vix_ratio": {"raw": 1.09, "norm": -0.2},
                "pct_above_200dma": {"raw": 66.0, "norm": 0.3},
            },
        }
        out = _ensure_layer2_gate_votes(inputs)
        gate_inputs = [g["input"] for g in out["layer2_gate_votes"]]
        self.assertEqual(
            gate_inputs,
            [
                "mcclellan",
                "nh_nl_ratio",
                "hyg_lqd",
                "skew",
                "vix_ratio",
                "pct_above_200dma",
            ],
        )
        nh_nl = next(g for g in out["layer2_gate_votes"] if g["input"] == "nh_nl_ratio")
        self.assertIn("vote", nh_nl)
        self.assertIn("signal", nh_nl)
        self.assertIsInstance(out["layer2_gate_confirmed_count"], int)

    def test_preserves_existing_gate_votes(self) -> None:
        existing = [{"input": "nh_nl_ratio", "vote": False, "signal": "neutral"}]
        inputs = {"layer2_gate_votes": existing, "layer2_components": {"nh_nl_ratio": {"norm": 0.1}}}
        out = _ensure_layer2_gate_votes(inputs)
        self.assertIs(out["layer2_gate_votes"], existing)


if __name__ == "__main__":
    unittest.main()
