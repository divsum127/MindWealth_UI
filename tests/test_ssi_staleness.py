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

import yaml

from src.config_paths import SSI_CONFIG
from src.sentiment_superindex.config import staleness_policy, weight_penalty_for
from src.sentiment_superindex.data.alignment import align_to_daily, calendar_day_index, max_stale_days_for_cadence
from src.sentiment_superindex.data.staleness import observation_as_of
from src.sentiment_superindex.engine.superindex import build_layer1


class TestSSIStaleness(unittest.TestCase):
    def test_policy_comes_from_yaml_not_a_code_copy(self) -> None:
        """The YAML is the single source: the resolved policy must equal the file verbatim.

        Asserting against literals here is what previously let code and config drift while
        both tests passed (audit 2026-08-18). This compares the two directly instead.
        """
        block = yaml.safe_load(SSI_CONFIG.read_text(encoding="utf-8"))["staleness"]
        max_days, default_penalty, overrides = staleness_policy()
        self.assertEqual(max_days, {k: int(v) for k, v in block["max_stale_days"].items()})
        self.assertAlmostEqual(default_penalty, float(block["weight_penalty"]))
        self.assertEqual(
            overrides,
            {k: float(v) for k, v in (block.get("weight_penalty_by_signal") or {}).items()},
        )

    def test_staleness_policy_matches_rohit_c46_signoff(self) -> None:
        """Guards the shipped values (sheet C46 / Test 21, 2026-08-07) against silent edits."""
        max_days, default_penalty, overrides = staleness_policy()
        self.assertEqual(max_days["weekly"], 8)
        self.assertEqual(max_days["monthly"], 30)
        self.assertEqual(max_days["daily"], 3)
        self.assertAlmostEqual(default_penalty, 0.8)
        self.assertAlmostEqual(overrides["aaii_spread"], 1.0)
        self.assertAlmostEqual(overrides["cftc_fm_net"], 0.18)

    def test_missing_staleness_block_raises_rather_than_defaulting(self) -> None:
        """A config without the block must fail loudly, never score on a code fallback."""
        staleness_policy.cache_clear()
        with patch("src.sentiment_superindex.config.load_config", return_value={}):
            with self.assertRaises(ValueError):
                staleness_policy()
        staleness_policy.cache_clear()
        self.assertEqual(staleness_policy()[0]["weekly"], 8)

    def test_per_signal_penalty_aaii_no_decay(self) -> None:
        series = pd.Series([10.0], index=pd.DatetimeIndex(["2026-01-01"]))
        raw, stale_days, mult = observation_as_of(series, pd.Timestamp("2026-01-03"), series_key="aaii_spread")
        self.assertEqual(raw, 10.0)
        self.assertEqual(stale_days, 2)
        self.assertAlmostEqual(mult, 1.0)
        self.assertAlmostEqual(weight_penalty_for("aaii_spread"), 1.0)

    def test_per_signal_penalty_cftc_fm_decay(self) -> None:
        series = pd.Series([-300_000.0], index=pd.DatetimeIndex(["2026-07-28"]))
        raw, stale_days, mult = observation_as_of(
            series, pd.Timestamp("2026-08-04"), series_key="cftc_fm_net"
        )
        self.assertEqual(raw, -300_000.0)
        self.assertEqual(stale_days, 7)
        self.assertAlmostEqual(mult, 0.18)

    def test_cftc_weekly_dropped_after_eight_days(self) -> None:
        series = pd.Series([10.0], index=pd.DatetimeIndex(["2026-01-01"]))
        raw, stale_days, mult = observation_as_of(series, pd.Timestamp("2026-01-10"), series_key="aaii_spread")
        self.assertIsNone(raw)
        self.assertEqual(stale_days, 9)
        self.assertEqual(mult, 0.0)

    def test_monthly_allows_30_calendar_days(self) -> None:
        series = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-01"]))
        raw, stale_days, mult = observation_as_of(series, pd.Timestamp("2026-01-30"), series_key="margin_debt")
        self.assertEqual(raw, 1.0)
        self.assertEqual(stale_days, 29)
        self.assertAlmostEqual(mult, 0.8)

    def test_monthly_dropped_after_30_days(self) -> None:
        series = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-01"]))
        raw, stale_days, _ = observation_as_of(series, pd.Timestamp("2026-02-01"), series_key="margin_debt")
        self.assertIsNone(raw)
        self.assertEqual(stale_days, 31)

    def test_daily_allows_three_calendar_days(self) -> None:
        series = pd.Series([50.0], index=pd.DatetimeIndex(["2026-01-02"]))
        raw, stale_days, mult = observation_as_of(series, pd.Timestamp("2026-01-05"), series_key="cnn_fg")
        self.assertEqual(raw, 50.0)
        self.assertEqual(stale_days, 3)
        self.assertAlmostEqual(mult, 1.0)

    def test_daily_dropped_after_three_days(self) -> None:
        series = pd.Series([50.0], index=pd.DatetimeIndex(["2026-01-02"]))
        raw, stale_days, _ = observation_as_of(series, pd.Timestamp("2026-01-06"), series_key="cnn_fg")
        self.assertIsNone(raw)
        self.assertEqual(stale_days, 4)

    def test_align_to_daily_monthly_uses_30_not_5(self) -> None:
        obs = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-01"]))
        cal = calendar_day_index("2026-01-02", "2026-02-01")
        out = align_to_daily(obs, cal, cadence="monthly")
        self.assertEqual(out.notna().sum(), 30)
        weekly_out = align_to_daily(obs, cal, cadence="weekly")
        self.assertEqual(weekly_out.notna().sum(), 8)

    def test_max_stale_days_for_cadence(self) -> None:
        self.assertEqual(max_stale_days_for_cadence("weekly"), 8)
        self.assertEqual(max_stale_days_for_cadence("monthly"), 30)
        self.assertEqual(max_stale_days_for_cadence("daily"), 3)

    @patch("src.sentiment_superindex.engine.superindex.load_all_series")
    def test_stale_aaii_keeps_full_effective_weight_with_no_penalty(self, mock_load) -> None:
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
            "margin_debt": pd.Series([500.0] * len(idx), index=idx),
        }

        l1 = build_layer1("2026-01-05")
        cov = l1["signal_coverage"]
        self.assertIn("aaii_spread", cov["stale"])
        eff = cov["effective_weights"]["aaii_spread"]
        self.assertAlmostEqual(eff, cov["nominal_weights"]["aaii_spread"], places=4)


if __name__ == "__main__":
    unittest.main()
