"""SSI VIX ratio orientation: VIX/VIX3M must match stress/complacency thresholds.

The fetch is patched at ``cached_yahoo_close`` (not the raw ``fetch_yahoo_close``) because
the legs are read through the disk cache since 2026-08-18 -- see
``sentiment_superindex.data.yahoo_cache`` for why an uncached join lost the whole series when
one leg came back truncated.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.data.yahoo_inputs import vix_ratio_series
from src.sentiment_superindex.engine.layer2 import evaluate_layer2


class TestVixRatioSeries(unittest.TestCase):
    @patch("src.sentiment_superindex.data.yahoo_inputs.cached_yahoo_close")
    def test_formula_is_vix_over_vix3m(self, mock_fetch):
        idx = pd.to_datetime(["2024-06-24"])
        mock_fetch.side_effect = lambda ticker, start="2007-01-01": (
            pd.Series([18.0], index=idx, name=ticker)
            if ticker == "^VIX"
            else pd.Series([19.8], index=idx, name=ticker)
        )
        ratio = vix_ratio_series("2024-01-01")
        self.assertAlmostEqual(float(ratio.iloc[0]), 18.0 / 19.8, places=6)

    @patch("src.sentiment_superindex.data.yahoo_inputs.cached_yahoo_close")
    def test_mild_contango_not_above_one(self, mock_fetch):
        """Rohit case: VIX3M/VIX ~1.06 contango → VIX/VIX3M ~0.94, not backwardation."""
        idx = pd.to_datetime(["2024-06-24"])
        vix = 18.0
        vix3m = 18.0 * 1.06  # mild contango in VIX3M/VIX terms
        mock_fetch.side_effect = lambda ticker, start="2007-01-01": (
            pd.Series([vix], index=idx, name=ticker)
            if ticker == "^VIX"
            else pd.Series([vix3m], index=idx, name=ticker)
        )
        ratio = float(vix_ratio_series("2024-01-01").iloc[0])
        self.assertLess(ratio, 1.0)
        self.assertAlmostEqual(ratio, 1.0 / 1.06, places=4)


class TestVixRatioLayer2Votes(unittest.TestCase):
    @patch("src.sentiment_superindex.engine.layer2.load_all_series")
    @patch("src.sentiment_superindex.engine.layer2.values_as_of")
    def test_mild_contango_neutral_not_stress(self, mock_vals, mock_series):
        """Normal contango (~0.94 VIX/VIX3M) must not flash stress/backwardation."""
        pd = __import__("pandas")
        idx = pd.date_range("2019-01-01", periods=100)
        hyg_history = pd.Series([0.5 + (i % 10) * 0.04 for i in range(100)], index=idx)
        mock_series.return_value = {
            "hyg_lqd": hyg_history,
            "dbmf_beta": pd.Series([0.7] * 100, index=idx),
            "cnn_fg": pd.Series([50] * 100, index=idx),
            "vix_ratio": pd.Series([0.94] * 100, index=idx),
        }
        mock_vals.return_value = {
            "hyg_lqd": 0.68,
            "dbmf_beta": 0.7,
            "cnn_fg": 50.0,
            "vix_ratio": 0.94,
        }
        _, _, votes, _ = evaluate_layer2("2020-06-01")
        vix_vote = next(v for v in votes if v["input"] == "vix_ratio")
        self.assertNotEqual(vix_vote["signal"], "stress")
        self.assertIn(vix_vote["signal"], ("neutral", "complacency"))

    @patch("src.sentiment_superindex.engine.layer2.load_all_series")
    @patch("src.sentiment_superindex.engine.layer2.values_as_of")
    def test_backwardation_triggers_stress(self, mock_vals, mock_series):
        pd = __import__("pandas")
        idx = pd.date_range("2019-01-01", periods=100)
        mock_series.return_value = {
            "hyg_lqd": pd.Series([0.7] * 100, index=idx),
            "dbmf_beta": pd.Series([0.5] * 100, index=idx),
            "cnn_fg": pd.Series([50] * 100, index=idx),
            "vix_ratio": pd.Series([1.08] * 100, index=idx),
        }
        mock_vals.return_value = {
            "hyg_lqd": 0.7,
            "dbmf_beta": 0.5,
            "cnn_fg": 50.0,
            "vix_ratio": 1.08,
        }
        _, _, votes, _ = evaluate_layer2("2020-06-01")
        vix_vote = next(v for v in votes if v["input"] == "vix_ratio")
        self.assertEqual(vix_vote["signal"], "stress")
        self.assertTrue(vix_vote["vote"])


if __name__ == "__main__":
    unittest.main()
