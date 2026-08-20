"""Tests for margin debt FRED pull."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.data.margin_debt_pull import fetch_margin_debt
from src.sentiment_superindex.data.pull_all import load_all_series


class TestMarginDebtPull(unittest.TestCase):
    @patch("src.sentiment_superindex.data.margin_debt_pull._fetch_fred_margin_debt")
    @patch("src.sentiment_superindex.data.margin_debt_pull.load_cached_series")
    def test_fetch_margin_debt_merges_cache_and_live(self, mock_cache, mock_live) -> None:
        mock_cache.return_value = pd.Series([100.0], index=pd.DatetimeIndex(["2020-01-01"]))
        mock_live.return_value = pd.Series([110.0], index=pd.DatetimeIndex(["2020-02-01"]))
        s = fetch_margin_debt()
        self.assertEqual(len(s), 2)
        self.assertEqual(s.name, "margin_debt")

    @patch("src.sentiment_superindex.data.margin_debt_pull.fetch_margin_debt")
    def test_load_all_series_includes_margin_debt(self, mock_margin) -> None:
        mock_margin.return_value = pd.Series([1.0], index=pd.DatetimeIndex(["2020-01-01"]))
        with patch("src.sentiment_superindex.data.pull_all.hyg_lqd_ratio", return_value=pd.Series(dtype=float)), patch(
            "src.sentiment_superindex.data.pull_all.dbmf_beta_vs_spy", return_value=pd.Series(dtype=float)
        ), patch("src.sentiment_superindex.data.pull_all.load_cnn_series", return_value=pd.Series(dtype=float)), patch(
            "src.sentiment_superindex.data.pull_all.vix_ratio_series", return_value=pd.Series(dtype=float)
        ), patch("src.sentiment_superindex.data.pull_all.fetch_aaii_spread", return_value=pd.Series(dtype=float)), patch(
            "src.sentiment_superindex.data.pull_all.fetch_naaim_exposure", return_value=pd.Series(dtype=float)
        ), patch("src.sentiment_superindex.data.pull_all.fetch_put_call_ema", return_value=pd.Series(dtype=float)), patch(
            "src.sentiment_superindex.data.pull_all.fetch_pct_above_200dma", return_value=pd.Series(dtype=float)
        ), patch("src.sentiment_superindex.data.pull_all.fetch_mcclellan_oscillator", return_value=pd.Series(dtype=float)), patch(
            "src.sentiment_superindex.data.pull_all.fetch_skew", return_value=pd.Series(dtype=float)
        ), patch("src.sentiment_superindex.data.pull_all.fetch_nh_nl_ratio", return_value=pd.Series(dtype=float)), patch(
            "src.sentiment_superindex.data.pull_all.fetch_cftc_fast_money_net", return_value=pd.Series(dtype=float)
        ), patch("src.sentiment_superindex.data.pull_all.fetch_cftc_asset_manager_net", return_value=pd.Series(dtype=float)):
            load_all_series(force=True)
        self.assertIn("margin_debt", load_all_series())


if __name__ == "__main__":
    unittest.main()
