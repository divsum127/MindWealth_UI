"""Tests for CAPE/CFTC source freshness vs report date."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data.source_freshness import (
    check_cape_freshness,
    check_cftc_freshness,
    ensure_cape_cftc_fresh,
    expected_latest_cftc_tuesday,
)


class TestExpectedCftcTuesday(unittest.TestCase):
    def test_jun_16_2026_expects_jun_9(self) -> None:
        exp = expected_latest_cftc_tuesday("2026-06-16")
        self.assertEqual(exp.strftime("%Y-%m-%d"), "2026-06-09")

    def test_jun_12_2026_friday_expects_jun_9(self) -> None:
        exp = expected_latest_cftc_tuesday("2026-06-12")
        self.assertEqual(exp.strftime("%Y-%m-%d"), "2026-06-09")


class TestCapeFreshness(unittest.TestCase):
    def test_stale_when_lag_exceeds_threshold(self) -> None:
        idx = pd.to_datetime(["2026-06-04"])
        cape = pd.Series([42.7], index=idx)
        row = check_cape_freshness("2026-06-16", cape)
        self.assertTrue(row.stale)
        self.assertEqual(row.lag_days, 12)
        self.assertEqual(row.source_date, "2026-06-04")

    def test_fresh_when_within_threshold(self) -> None:
        idx = pd.to_datetime(["2026-06-12"])
        cape = pd.Series([42.7], index=idx)
        row = check_cape_freshness("2026-06-16", cape)
        self.assertFalse(row.stale)
        self.assertEqual(row.lag_days, 4)


class TestCftcFreshness(unittest.TestCase):
    def test_stale_when_older_than_expected_tuesday(self) -> None:
        idx = pd.to_datetime(["2026-06-02"])
        cftc = pd.Series([-503509.0], index=idx)
        row = check_cftc_freshness("2026-06-16", cftc)
        self.assertTrue(row.stale)
        self.assertEqual(row.expected_source_date, "2026-06-09")

    def test_fresh_when_matches_expected(self) -> None:
        idx = pd.to_datetime(["2026-06-09"])
        cftc = pd.Series([-459690.0], index=idx)
        row = check_cftc_freshness("2026-06-16", cftc)
        self.assertFalse(row.stale)


class TestEnsureFresh(unittest.TestCase):
    @patch("src.macro_intelligence.data.source_freshness.force_refresh_cftc_zip", return_value=False)
    @patch("src.macro_intelligence.data.source_freshness.fetch_cftc_fast_money_net")
    @patch("src.macro_intelligence.data.source_freshness.refresh_cftc_zip_if_stale")
    @patch("src.macro_intelligence.data.source_freshness.fetch_cape_history")
    @patch("src.macro_intelligence.data.source_freshness.load_cape_series")
    def test_cape_refresh_on_stale(
        self,
        mock_load_cape,
        mock_fetch_cape,
        mock_cftc_refresh,
        mock_cftc_fetch,
        mock_force_cftc,
    ) -> None:
        stale = pd.Series([42.0], index=pd.to_datetime(["2026-06-01"]))
        fresh = pd.Series([42.7], index=pd.to_datetime(["2026-06-12"]))
        mock_load_cape.return_value = stale
        mock_fetch_cape.return_value = fresh
        cftc = pd.Series([-459690.0], index=pd.to_datetime(["2026-06-09"]))
        mock_cftc_fetch.return_value = cftc

        audit = ensure_cape_cftc_fresh("2026-06-16")
        mock_fetch_cape.assert_called_once()
        self.assertTrue(audit["sources"]["CAPE"]["refreshed"])
        self.assertFalse(audit["sources"]["CFTC"]["stale"])


if __name__ == "__main__":
    unittest.main()
