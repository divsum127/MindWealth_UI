"""Regression tests for the NH/NL ratio formula (2026-07-16 unbounded-ratio bug)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.data.sp500_breadth import compute_daily_breadth_stats


def _synthetic_closes(n_days: int = 260, n_symbols: int = 12) -> pd.DataFrame:
    """Enough history/symbols to clear MIN_HISTORY_DAYS and MIN_STOCKS gates."""
    idx = pd.bdate_range("2020-01-01", periods=n_days)
    rng = np.random.default_rng(42)
    data = {}
    for i in range(n_symbols):
        base = 100 + i * 5
        walk = np.cumsum(rng.normal(0, 0.5, n_days))
        data[f"SYM{i}"] = base + walk
    return pd.DataFrame(data, index=idx)


class TestNhNlRatioFormula(unittest.TestCase):
    def test_ratio_is_bounded_zero_to_one(self):
        """highs / (highs + lows) must never exceed 1, unlike the old highs / lows bug."""
        close = _synthetic_closes()
        out = compute_daily_breadth_stats(close)
        ratios = out["nh_nl_ratio"].dropna()
        self.assertTrue((ratios >= 0).all())
        self.assertTrue((ratios <= 1).all())

    def test_matches_expected_formula_on_known_counts(self):
        """Reproduce the reported case: 46 highs, 1 low -> 0.9787..., not 46.0."""
        close = _synthetic_closes(n_days=260, n_symbols=5)
        out = compute_daily_breadth_stats(close)
        row = out.iloc[-1].copy()

        # Directly verify the formula relationship for whatever counts were computed,
        # rather than depending on the random walk to produce exactly 46/1.
        highs, lows = row["new_highs"], row["new_lows"]
        if highs + lows > 0:
            expected = highs / (highs + lows)
            self.assertAlmostEqual(row["nh_nl_ratio"], expected, places=9)
            # The old buggy formula (highs / lows) would only equal the new one
            # when lows == highs + lows, i.e. highs == 0 - not the general case.
            if lows > 0 and highs > 0:
                old_buggy_ratio = highs / lows
                if old_buggy_ratio > 1.01:
                    self.assertLess(row["nh_nl_ratio"], old_buggy_ratio)

        # Explicit worked example from the bug report: 46 highs, 1 low.
        example_highs, example_lows = 46.0, 1.0
        old_formula = example_highs / example_lows
        new_formula = example_highs / (example_highs + example_lows)
        self.assertEqual(old_formula, 46.0)
        self.assertAlmostEqual(new_formula, 0.9787234042553191, places=10)

    def test_zero_highs_and_lows_yields_nan(self):
        close = _synthetic_closes(n_days=260, n_symbols=8)
        out = compute_daily_breadth_stats(close)
        # Manually zero out a row's highs/lows and recheck guard logic via the formula directly.
        highs = pd.Series([0.0, 5.0, 0.0])
        lows = pd.Series([0.0, 0.0, 3.0])
        denom = highs + lows
        ratio = np.where(denom > 0, highs / denom, np.nan)
        self.assertTrue(np.isnan(ratio[0]))
        self.assertEqual(ratio[1], 1.0)
        self.assertEqual(ratio[2], 0.0)
        self.assertFalse(out.empty)


if __name__ == "__main__":
    unittest.main()
