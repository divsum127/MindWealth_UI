"""Percentile engine unit tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.percentiles import percentile_rank, compute_pctile_for_series
from src.macro_intelligence.data.cftc_pull import _rolling_pctile, describe_cftc_pctile_window
from src.macro_intelligence.models import SignalTier
from src.macro_intelligence.engine.percentiles import evaluate_variable_tier


class TestPercentiles(unittest.TestCase):
    def test_percentile_rank_extreme_high(self):
        hist = pd.Series(np.linspace(0, 100, 101))
        p = percentile_rank(99.0, hist)
        self.assertIsNotNone(p)
        self.assertGreater(p, 95)

    def test_percentile_rank_is_not_minmax_scaling(self):
        """Outlier compresses min-max position but not true rank."""
        hist = pd.Series([-100.0, -90.0, -80.0, -70.0, -60.0, 500.0])
        value = -65.0
        rank = percentile_rank(value, hist)
        roll_min, roll_max = float(hist.min()), float(hist.max())
        minmax = (value - roll_min) / (roll_max - roll_min) * 100
        self.assertIsNotNone(rank)
        self.assertAlmostEqual(rank, 4 / 6 * 100, places=5)  # four of six readings <= -65
        self.assertAlmostEqual(minmax, 35 / 600 * 100, places=5)
        self.assertNotAlmostEqual(rank, minmax, places=1)

    def test_rolling_pctile_matches_percentile_rank(self):
        idx = pd.date_range("2023-01-06", periods=160, freq="W-FRI")
        values = np.linspace(-500_000, -200_000, 160)
        series = pd.Series(values, index=idx)
        as_of = idx[-1]
        got = _rolling_pctile(series, as_of, weeks=156)
        window = series.loc[:as_of].dropna().tail(156)
        expected = percentile_rank(float(series.loc[as_of]), window)
        self.assertAlmostEqual(got, expected, places=5)

    def test_describe_cftc_pctile_window_sign_distribution(self):
        idx = pd.date_range("2023-01-06", periods=156, freq="W-FRI")
        series = pd.Series(np.linspace(-500_000, -200_000, 156), index=idx)
        diag = describe_cftc_pctile_window(series, idx[-1], weeks=156)
        self.assertEqual(diag["n"], 156)
        self.assertEqual(diag["sign_negative"], 156)
        self.assertEqual(diag["sign_positive"], 0)
        self.assertIsNotNone(diag["percentile_rank"])
        self.assertEqual(diag["current"], float(series.iloc[-1]))

    def test_vix_rare_tier(self):
        cfg = {
            "paradigm": "DUAL",
            "rare": {"abs_level": 25, "high_pctile": 80},
            "extreme": {"abs_level": 35, "high_pctile": 95},
        }
        tier, direction = evaluate_variable_tier("VIX", cfg, 33.6, 85.0)
        self.assertEqual(tier, SignalTier.RARE)
        self.assertEqual(direction, "UP")

    def test_vix_single_day_spike_escalates_to_rare_below_abs_level(self):
        """T-03 regression (2026-06-06 audit): Jun 5 2026 VIX 15.40 -> 21.51 (+39.68%) stayed
        NORMAL because 21.51 is below the RARE abs_level (25.0). A 25%+ one-day jump must now
        escalate to at least RARE regardless of the absolute level/percentile."""
        cfg = {
            "paradigm": "DUAL",
            "rare": {"abs_level": 25, "high_pctile": 80, "single_day_pct_change": 0.25},
            "extreme": {"abs_level": 35, "high_pctile": 95, "single_day_pct_change": 0.40},
        }
        tier, direction = evaluate_variable_tier(
            "VIX", cfg, 21.51, 60.0, meta={"single_day_pct_change": 0.3968},
        )
        self.assertEqual(tier, SignalTier.RARE)
        self.assertEqual(direction, "UP")

    def test_vix_single_day_spike_escalates_to_extreme_at_40pct(self):
        cfg = {
            "paradigm": "DUAL",
            "rare": {"abs_level": 25, "high_pctile": 80, "single_day_pct_change": 0.25},
            "extreme": {"abs_level": 35, "high_pctile": 95, "single_day_pct_change": 0.40},
        }
        tier, direction = evaluate_variable_tier(
            "VIX", cfg, 21.51, 60.0, meta={"single_day_pct_change": 0.45},
        )
        self.assertEqual(tier, SignalTier.EXTREME)
        self.assertEqual(direction, "UP")

    def test_vix_moderate_single_day_move_escalates_to_rare(self):
        cfg = {
            "paradigm": "DUAL",
            "rare": {"abs_level": 25, "high_pctile": 80, "single_day_pct_change": 0.25},
            "extreme": {"abs_level": 35, "high_pctile": 95, "single_day_pct_change": 0.40},
        }
        tier, direction = evaluate_variable_tier(
            "VIX", cfg, 18.0, 60.0, meta={"single_day_pct_change": 0.28},
        )
        self.assertEqual(tier, SignalTier.RARE)
        self.assertEqual(direction, "UP")

    def test_vix_small_single_day_move_stays_normal(self):
        cfg = {
            "paradigm": "DUAL",
            "rare": {"abs_level": 25, "high_pctile": 80, "single_day_pct_change": 0.25},
            "extreme": {"abs_level": 35, "high_pctile": 95, "single_day_pct_change": 0.40},
        }
        tier, _direction = evaluate_variable_tier(
            "VIX", cfg, 16.0, 40.0, meta={"single_day_pct_change": 0.05},
        )
        self.assertEqual(tier, SignalTier.NORMAL)

    def test_single_day_change_meta_helper(self):
        from src.macro_intelligence.data.pull_all import _single_day_change_meta

        hist = pd.Series([15.40, 21.51], index=pd.to_datetime(["2026-06-04", "2026-06-05"]))
        meta = _single_day_change_meta("VIX", hist, 21.51)
        self.assertAlmostEqual(meta["single_day_pct_change"], (21.51 - 15.40) / 15.40, places=6)
        self.assertEqual(meta["prior_close"], 15.40)

    def test_single_day_change_meta_helper_ignores_non_vix(self):
        from src.macro_intelligence.data.pull_all import _single_day_change_meta

        hist = pd.Series([15.40, 21.51], index=pd.to_datetime(["2026-06-04", "2026-06-05"]))
        self.assertEqual(_single_day_change_meta("HY", hist, 21.51), {})


if __name__ == "__main__":
    unittest.main()
