"""SSI Layer 2 vote tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.engine.layer2 import evaluate_layer2


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


if __name__ == "__main__":
    unittest.main()
