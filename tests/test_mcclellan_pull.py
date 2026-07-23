"""Regression tests for the McClellan oscillator formula (2026-07-16 cumsum bug)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.data.mcclellan_pull import _classic_mcclellan


class TestClassicMcClellan(unittest.TestCase):
    def test_does_not_cumsum_input(self):
        """EMA must run on the daily net-advances series, not its running total.

        A constant daily net-advances series has EMA(19) == EMA(39) == that
        constant, so the oscillator converges to 0. If cumsum() were applied
        first, the AD line would grow without bound and the oscillator would
        blow up instead of converging near zero.
        """
        idx = pd.bdate_range("2020-01-01", periods=200)
        net_advances = pd.Series([20.0] * len(idx), index=idx)
        osc = _classic_mcclellan(net_advances)
        self.assertLess(abs(osc.iloc[-1]), 1.0)

    def test_stays_within_normal_band_for_realistic_input(self):
        """Realistic daily net-advances (small values) must stay inside ~±150."""
        idx = pd.bdate_range("2020-01-01", periods=300)
        # Realistic S&P 500 daily advancers-minus-decliners noise, not a running total.
        values = [((-1) ** i) * (10 + (i % 7) * 3) for i in range(len(idx))]
        net_advances = pd.Series(values, index=idx, dtype=float)
        osc = _classic_mcclellan(net_advances)
        self.assertTrue((osc.abs() < 150).all())

    def test_matches_manual_ema_formula(self):
        idx = pd.bdate_range("2020-01-01", periods=100)
        net_advances = pd.Series(range(-50, 50), index=idx, dtype=float)
        osc = _classic_mcclellan(net_advances)

        expected_ema19 = net_advances.ewm(span=19, adjust=False).mean()
        expected_ema39 = net_advances.ewm(span=39, adjust=False).mean()
        expected = (expected_ema19 - expected_ema39).dropna()

        pd.testing.assert_series_equal(osc, expected.astype(float), check_names=False)

    def test_handles_nan_as_zero(self):
        idx = pd.bdate_range("2020-01-01", periods=50)
        values = [5.0] * 25 + [float("nan")] * 25
        net_advances = pd.Series(values, index=idx)
        osc = _classic_mcclellan(net_advances)
        self.assertFalse(osc.isna().any())


class TestMcClellanDisplayRounding(unittest.TestCase):
    def test_positioning_rounds_mcclellan_to_two_decimals(self):
        from src.sentiment_superindex.engine.positioning import _round_display

        self.assertEqual(_round_display(217.09514599086106), 217.1)
        self.assertEqual(_round_display(12.160863139182467), 12.16)
        self.assertIsNone(_round_display(None))


if __name__ == "__main__":
    unittest.main()
