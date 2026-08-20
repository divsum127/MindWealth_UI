"""SSI Layer 2 vote tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.engine.layer2 import (
    evaluate_layer2,
    evaluate_layer2_gates,
    derive_layer2_sizing,
    summarize_layer2_gate_votes,
)


class TestSSILayer2(unittest.TestCase):
    @patch("src.sentiment_superindex.engine.layer2.load_all_series")
    @patch("src.sentiment_superindex.engine.layer2.values_as_of")
    def test_confirmed_two_votes(self, mock_vals, mock_series):
        mock_series.return_value = {
            "hyg_lqd": __import__("pandas").Series([0.7, 0.75], index=__import__("pandas").date_range("2020-01-01", periods=2)),
            "dbmf_beta": __import__("pandas").Series([0.3], index=__import__("pandas").date_range("2020-01-01", periods=1)),
            "cnn_fg": __import__("pandas").Series([20], index=__import__("pandas").date_range("2020-01-01", periods=1)),
            "vix_ratio": __import__("pandas").Series([1.15], index=__import__("pandas").date_range("2020-01-01", periods=1)),
        }
        mock_vals.return_value = {"hyg_lqd": 0.75, "dbmf_beta": 0.3, "cnn_fg": 20.0, "vix_ratio": 1.15}
        status, count, votes, mult = evaluate_layer2("2020-06-01")
        self.assertEqual(status, "CONFIRMED")
        self.assertGreaterEqual(count, 2)
        self.assertAlmostEqual(mult, 1.2)

    @patch("src.sentiment_superindex.engine.layer2.load_all_series")
    @patch("src.sentiment_superindex.engine.layer2.values_as_of")
    def test_unconfirmed(self, mock_vals, mock_series):
        pd = __import__("pandas")
        idx = pd.date_range("2019-01-01", periods=100)
        mock_series.return_value = {
            "hyg_lqd": pd.Series([0.5 + (i % 10) * 0.04 for i in range(100)], index=idx),
            "dbmf_beta": pd.Series([0.7] * 100, index=idx),
            "cnn_fg": pd.Series([50] * 100, index=idx),
            "vix_ratio": pd.Series([1.02] * 100, index=idx),
        }
        mock_vals.return_value = {"hyg_lqd": 0.68, "dbmf_beta": 0.7, "cnn_fg": 50.0, "vix_ratio": 1.02}
        status, count, _, mult = evaluate_layer2("2020-06-01")
        self.assertEqual(count, 0)
        self.assertEqual(status, "UNCONFIRMED")
        self.assertAlmostEqual(mult, 0.8)


class TestSSILayer2Gates(unittest.TestCase):
    def test_all_six_gates_include_mcclellan_vote(self):
        layer2_components = {
            "mcclellan": {"raw": -12.0, "norm": -0.6},
            "nh_nl_ratio": {"raw": 0.73, "norm": -0.1},
            "hyg_lqd": {"raw": 0.75, "norm": 1.2},
            "skew": {"raw": 150.0, "norm": -0.8},
            "vix_ratio": {"raw": 1.09, "norm": -0.2},
            "pct_above_200dma": {"raw": 66.0, "norm": 0.3},
        }
        legacy_votes = [
            {"input": "hyg_lqd", "raw": 0.75, "vote": True, "signal": "risk_on", "pctile": 100.0},
            {"input": "vix_ratio", "raw": 1.09, "vote": True, "signal": "stress"},
        ]
        gates = evaluate_layer2_gates(layer2_components, legacy_votes=legacy_votes)
        inputs = [g["input"] for g in gates.votes]
        self.assertEqual(
            inputs,
            [
                "mcclellan",
                "nh_nl_ratio",
                "hyg_lqd",
                "skew",
                "vix_ratio",
                "pct_above_200dma",
            ],
        )
        mcc = next(g for g in gates.votes if g["input"] == "mcclellan")
        self.assertTrue(mcc["vote"])
        self.assertEqual(mcc["signal"], "bearish")
        self.assertEqual(mcc["side"], "short")
        self.assertEqual(gates.conf_long, 1)
        self.assertEqual(gates.conf_short, 3)
        self.assertEqual(gates.direction, "SHORT_CONFIRMED")
        self.assertGreaterEqual(gates.confirmed_count, 3)

    def test_nh_nl_high_raw_low_norm_is_bearish_gate(self) -> None:
        """Raw NH share can exceed 0.5 while z-scored norm stays negative (weak vs history)."""
        layer2_components = {
            "mcclellan": {"raw": 0.0, "norm": 0.0},
            "nh_nl_ratio": {"raw": 0.57, "norm": -0.60},
            "hyg_lqd": {"raw": 0.7, "norm": 0.0},
            "skew": {"raw": 140.0, "norm": 0.0},
            "vix_ratio": {"raw": 1.0, "norm": 0.0},
            "pct_above_200dma": {"raw": 55.0, "norm": 0.0},
        }
        gates = evaluate_layer2_gates(layer2_components)
        nh = next(g for g in gates.votes if g["input"] == "nh_nl_ratio")
        self.assertTrue(nh["vote"])
        self.assertEqual(nh["signal"], "bearish")
        self.assertEqual(nh["side"], "short")

    def test_nh_nl_positive_norm_is_bullish_gate(self) -> None:
        layer2_components = {
            "mcclellan": {"raw": 0.0, "norm": 0.0},
            "nh_nl_ratio": {"raw": 0.57, "norm": 0.57},
            "hyg_lqd": {"raw": 0.7, "norm": 0.0},
            "skew": {"raw": 140.0, "norm": 0.0},
            "vix_ratio": {"raw": 1.0, "norm": 0.0},
            "pct_above_200dma": {"raw": 55.0, "norm": 0.0},
        }
        gates = evaluate_layer2_gates(layer2_components)
        nh = next(g for g in gates.votes if g["input"] == "nh_nl_ratio")
        self.assertTrue(nh["vote"])
        self.assertEqual(nh["signal"], "bullish")
        self.assertEqual(nh["side"], "long")

    def test_mixed_directions_do_not_confirm(self) -> None:
        gate_votes = [
            {"input": "mcclellan", "vote": True, "signal": "bearish"},
            {"input": "hyg_lqd", "vote": True, "signal": "risk_on"},
            {"input": "vix_ratio", "vote": True, "signal": "stress"},
        ]
        summary = summarize_layer2_gate_votes(gate_votes, gate_total=6, min_confirmed=2)
        self.assertEqual(summary.conf_long, 1)
        self.assertEqual(summary.conf_short, 2)
        self.assertEqual(summary.direction, "SHORT_CONFIRMED")
        self.assertIn("1 long / 2 short of 6", summary.label)

        mixed = [
            {"input": "mcclellan", "vote": True, "signal": "bearish"},
            {"input": "hyg_lqd", "vote": True, "signal": "risk_on"},
            {"input": "skew", "vote": True, "signal": "bullish"},
        ]
        mixed_summary = summarize_layer2_gate_votes(mixed, gate_total=6, min_confirmed=2)
        self.assertEqual(mixed_summary.conf_long, 2)
        self.assertEqual(mixed_summary.conf_short, 1)
        self.assertEqual(mixed_summary.direction, "LONG_CONFIRMED")
        self.assertEqual(mixed_summary.confirmed_count, 3)

        split = [
            {"input": "mcclellan", "vote": True, "signal": "bearish"},
            {"input": "hyg_lqd", "vote": True, "signal": "risk_on"},
        ]
        split_summary = summarize_layer2_gate_votes(split, gate_total=6, min_confirmed=2)
        self.assertEqual(split_summary.direction, "UNCONFIRMED")
        self.assertIn("no direction confirmed", split_summary.label)


class TestDeriveLayer2Sizing(unittest.TestCase):
    def test_long_confirmed_maps_to_confirmed_mult(self):
        from src.sentiment_superindex.engine.layer2 import Layer2GateSummary

        summary = Layer2GateSummary(
            confirmed_count=3,
            conf_long=3,
            conf_short=0,
            gate_total=6,
            direction="LONG_CONFIRMED",
            label="L2: 3 long / 0 short of 6 - long confirmed",
            votes=[],
        )
        status, count, mult = derive_layer2_sizing(summary)
        self.assertEqual(status, "CONFIRMED")
        self.assertEqual(count, 3)
        self.assertAlmostEqual(mult, 1.2)

    def test_contested_maps_to_partial(self):
        from src.sentiment_superindex.engine.layer2 import Layer2GateSummary

        summary = Layer2GateSummary(
            confirmed_count=4,
            conf_long=2,
            conf_short=2,
            gate_total=6,
            direction="CONTESTED",
            label="contested",
            votes=[],
        )
        status, _, mult = derive_layer2_sizing(summary)
        self.assertEqual(status, "PARTIAL")
        self.assertAlmostEqual(mult, 1.0)

    def test_unconfirmed_maps_to_low_mult(self):
        from src.sentiment_superindex.engine.layer2 import Layer2GateSummary

        summary = Layer2GateSummary(
            confirmed_count=1,
            conf_long=1,
            conf_short=0,
            gate_total=6,
            direction="UNCONFIRMED",
            label="unconfirmed",
            votes=[],
        )
        status, _, mult = derive_layer2_sizing(summary)
        self.assertEqual(status, "UNCONFIRMED")
        self.assertAlmostEqual(mult, 0.8)


if __name__ == "__main__":
    unittest.main()
