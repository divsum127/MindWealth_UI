"""Unit tests for forward-fill alignment helpers (calendar vs business day limits)."""

from __future__ import annotations

import unittest

import pandas as pd

from src.sentiment_superindex.data.alignment import (
    MAX_FFORWARD_FILL_BUSINESS_DAYS,
    MAX_FFORWARD_FILL_CALENDAR_DAYS,
    align_to_daily,
    business_day_index,
    calendar_day_index,
    forward_fill_weekly,
)


class TestSeriesAlignment(unittest.TestCase):
    def test_calendar_limit_counts_calendar_rows(self) -> None:
        # Fri observation; calendar index Sat–Wed (5 calendar rows after Fri)
        obs = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-02"]))  # Friday
        cal = calendar_day_index("2026-01-03", "2026-01-07")  # Sat–Wed
        out = align_to_daily(obs, cal, max_ffill_calendar_days=5)
        self.assertTrue(out.notna().all())
        out_capped = align_to_daily(obs, cal, max_ffill_calendar_days=4)
        self.assertTrue(pd.isna(out_capped.iloc[-1]))

    def test_business_limit_counts_business_rows(self) -> None:
        # Fri observation; business index Mon–Fri next week
        obs = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-02"]))  # Friday
        bidx = business_day_index("2026-01-05", "2026-01-09")  # Mon–Fri
        out = forward_fill_weekly(obs, bidx, max_ffill_business_days=5)
        self.assertTrue(out.notna().all())
        out_capped = forward_fill_weekly(obs, bidx, max_ffill_business_days=4)
        self.assertTrue(pd.isna(out_capped.iloc[-1]))

    def test_business_vs_calendar_limit_diverge_over_weekend(self) -> None:
        """5 business days ≠ 5 calendar days when a weekend sits in between."""
        obs = pd.Series([42.0], index=pd.DatetimeIndex(["2026-01-02"]))  # Friday
        # 7 calendar days after Fri = through Fri Jan 9
        cal = calendar_day_index("2026-01-03", "2026-01-09")
        cal_out = align_to_daily(obs, cal, max_ffill_calendar_days=5)
        # Sat–Wed filled (5 cal days); Thu/Fri NaN
        self.assertEqual(cal_out.notna().sum(), 5)

        bidx = business_day_index("2026-01-05", "2026-01-09")
        biz_out = forward_fill_weekly(obs, bidx, max_ffill_business_days=5)
        self.assertTrue(biz_out.notna().all())

    def test_defaults_match_module_constants(self) -> None:
        # These are deprecated reference constants, NOT the live staleness policy. The
        # assertion below documents that they are intentionally decoupled from
        # SSI_CONFIG.yaml, so a future policy change does not quietly redefine them.
        self.assertEqual(MAX_FFORWARD_FILL_CALENDAR_DAYS, 5)
        self.assertEqual(MAX_FFORWARD_FILL_BUSINESS_DAYS, 5)
        from src.sentiment_superindex.config import staleness_policy

        self.assertNotEqual(staleness_policy()[0]["weekly"], MAX_FFORWARD_FILL_CALENDAR_DAYS)

    def test_monthly_cadence_default_allows_longer_carry(self) -> None:
        obs = pd.Series([1.0], index=pd.DatetimeIndex(["2026-01-01"]))
        cal = calendar_day_index("2026-01-02", "2026-01-20")
        out = align_to_daily(obs, cal, cadence="monthly")
        self.assertTrue(out.notna().all())

    def test_unlimited_forward_fill_when_limit_none(self) -> None:
        obs = pd.Series([1.0], index=pd.DatetimeIndex(["2020-01-01"]))
        cal = calendar_day_index("2020-01-02", "2020-06-01")
        out = align_to_daily(obs, cal, max_ffill_calendar_days=None)
        self.assertTrue(out.notna().all())


if __name__ == "__main__":
    unittest.main()
