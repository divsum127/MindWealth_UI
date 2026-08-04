"""SSI staleness caps and carried-forward weight penalties."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.config import MAX_STALE_DAYS, STALE_WEIGHT_PENALTY, staleness_policy
from src.sentiment_superindex.data.alignment import align_to_daily, calendar_day_index, max_stale_days_for_cadence
from src.sentiment_superindex.data.staleness import observation_as_of
from src.sentiment_superindex.engine.superindex import build_layer1


class TestSSIStaleness(unittest.TestCase):
    def test_config_constants_match_spec(self) -> None:
        self.assertEqual(MAX_STALE_DAYS["weekly"], 5)
        self.assertEqual(MAX_STALE_DAYS["daily"], 1)
        self.assertEqual(MAX_STALE_DAYS["monthly"], 25)
        self.assertAlmostEqual(STALE_WEIGHT_PENALTY, 0.8)

    def test_staleness_policy_loads_yaml(self) -> None:
        max_days, penalty = staleness_policy()
        self.assertEqual(max_days["monthly"], 25)
        self.assertAlmostEqual(penalty, 0.8)

    def test_weekly_within_max_carries_with_penalty(self) -> None:
        series = pd.Series([10.0], index=pd.DatetimeIndex(["2026-01-01"]))  # Thursday
        raw, stale_days, mult = observation_as_of(series, pd.Timestamp("2026-01-03"), series_key="aaii_spread")
        self.assertEqual(raw, 10.0)
        self.assertEqual(stale_days, 2)
        self.assertAlmostEqual(mult, 0.8)

    def test_weekly_beyond_max_dropped(self) -> None:
        series = pd.Series([10.0], index=pd.DatetimeIndex(["2026-01-01"]))
        raw, stale_days, mult = observation_as_of(series, pd.Timestamp("2026-01-08"), series_key="aaii_spread")
        self.assertIsNone(raw)
        self.assertEqual(stale_days, 7)
        self.assertEqual(mult, 0.0)

    def test_monthly_allows_25_calendar_days(self) -> None:
        series = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-01"]))
        raw, stale_days, mult = observation_as_of(series, pd.Timestamp("2026-01-25"), series_key="margin_debt")
        self.assertEqual(raw, 1.0)
        self.assertEqual(stale_days, 24)
        self.assertAlmostEqual(mult, 0.8)

    def test_monthly_dropped_after_25_days(self) -> None:
        series = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-01"]))
        raw, stale_days, _ = observation_as_of(series, pd.Timestamp("2026-01-27"), series_key="margin_debt")
        self.assertIsNone(raw)
        self.assertEqual(stale_days, 26)

    def test_align_to_daily_monthly_uses_25_not_5(self) -> None:
        obs = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-01"]))
        cal = calendar_day_index("2026-01-02", "2026-01-27")
        out = align_to_daily(obs, cal, cadence="monthly")
        self.assertEqual(out.notna().sum(), 25)
        weekly_out = align_to_daily(obs, cal, cadence="weekly")
        self.assertEqual(weekly_out.notna().sum(), 5)

    def test_max_stale_days_for_cadence(self) -> None:
        self.assertEqual(max_stale_days_for_cadence("monthly"), 25)
        self.assertEqual(max_stale_days_for_cadence("daily"), 1)

    @patch("src.sentiment_superindex.engine.superindex.load_all_series")
    def test_stale_aaii_gets_reduced_effective_weight(self, mock_load) -> None:
        idx = pd.bdate_range("2020-01-01", "2026-01-05")
        mock_load.return_value = {
            "aaii_spread": pd.Series([10.0], index=pd.DatetimeIndex(["2026-01-02"])),
            "naaim_exposure": pd.Series([80.0] * len(idx), index=idx),
            "put_call_ema": pd.Series([0.85] * len(idx), index=idx),
            "cnn_fg": pd.Series([50.0] * len(idx), index=idx),
            "pct_above_200dma": pd.Series([55.0] * len(idx), index=idx),
            "mcclellan": pd.Series([5.0] * len(idx), index=idx),
            "nh_nl_ratio": pd.Series([0.6] * len(idx), index=idx),
            "hyg_lqd": pd.Series([0.72] * len(idx), index=idx),
            "skew": pd.Series([130.0] * len(idx), index=idx),
            "vix_ratio": pd.Series([1.0] * len(idx), index=idx),
            "dbmf_beta": pd.Series([0.4] * len(idx), index=idx),
            "cftc_fm_net": pd.Series([100_000.0] * len(idx), index=idx),
            "cftc_rm_net": pd.Series([200_000.0] * len(idx), index=idx),
            "gross_net": pd.Series([300_000.0] * len(idx), index=idx),
        }

        l1 = build_layer1("2026-01-05")
        cov = l1["signal_coverage"]
        self.assertIn("aaii_spread", cov["stale"])
        eff = cov["effective_weights"]["aaii_spread"]
        # 30% nominal × 0.8 penalty vs fresh peers → below nominal, above raw 24% pre-renorm slice
        self.assertLess(eff, cov["nominal_weights"]["aaii_spread"])
        self.assertAlmostEqual(
            eff,
            0.30 * 0.8 / (0.30 * 0.8 + 0.35 + 0.20 + 0.15),
            places=3,
        )


if __name__ == "__main__":
    unittest.main()
