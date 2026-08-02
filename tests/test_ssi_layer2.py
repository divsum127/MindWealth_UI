"""SSI Layer 2 vote tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.engine.layer2 import evaluate_layer2, evaluate_layer2_gates


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
        confirmed, gates = evaluate_layer2_gates(layer2_components, legacy_votes=legacy_votes)
        inputs = [g["input"] for g in gates]
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
        mcc = next(g for g in gates if g["input"] == "mcclellan")
        self.assertTrue(mcc["vote"])
        self.assertEqual(mcc["signal"], "bearish")
        self.assertGreaterEqual(confirmed, 3)


if __name__ == "__main__":
    unittest.main()
