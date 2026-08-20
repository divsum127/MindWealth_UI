"""CFTC positioning pattern tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.data.cftc_patterns import evaluate_cftc_positioning


class _FreshnessRow:
    def __init__(self, *, stale: bool, source_date: str, expected_source_date: str):
        self.stale = stale
        self.source_date = source_date
        self.expected_source_date = expected_source_date


class TestCftcPatterns(unittest.TestCase):
    @patch("src.sentiment_superindex.data.cftc_patterns.check_cftc_freshness")
    def test_none_pattern_when_percentiles_neutral(self, mock_fresh):
        mock_fresh.return_value = _FreshnessRow(
            stale=False,
            source_date="2026-07-29",
            expected_source_date="2026-07-29",
        )
        out = evaluate_cftc_positioning(67.0, 61.0, "2026-08-04")
        self.assertEqual(out["positioning_pattern"], None)
        self.assertFalse(out["squeeze_setup"])
        self.assertFalse(out["liquidity_exit"])
        self.assertEqual(out["pattern_label"], "None")
        self.assertEqual(out["data_freshness"], "current")
        self.assertEqual(out["status"], "CONFIRMED")

    @patch("src.sentiment_superindex.data.cftc_patterns.check_cftc_freshness")
    def test_squeeze_pattern(self, mock_fresh):
        mock_fresh.return_value = _FreshnessRow(
            stale=False,
            source_date="2026-07-29",
            expected_source_date="2026-07-29",
        )
        # Placeholder cut (Rohit 13 Aug): FM<10 with no RM leg. RM is deliberately set to a value
        # that would have failed the retired RM>45 condition, to prove the leg is really gone.
        out = evaluate_cftc_positioning(8.0, 20.0, "2026-08-04")
        self.assertEqual(out["positioning_pattern"], "squeeze")
        self.assertTrue(out["squeeze_setup"])
        self.assertFalse(out["liquidity_exit"])
        self.assertEqual(out["pattern_label"], "Squeeze")
        self.assertIn("Fast money", out["plain_english"])

    @patch("src.sentiment_superindex.data.cftc_patterns.check_cftc_freshness")
    def test_liquidity_exit_pattern(self, mock_fresh):
        mock_fresh.return_value = _FreshnessRow(
            stale=False,
            source_date="2026-07-29",
            expected_source_date="2026-07-29",
        )
        # Placeholder cut: FM>=80, RM leg dropped. 60.0 RM would have failed the retired RM<30.
        out = evaluate_cftc_positioning(85.0, 60.0, "2026-08-04")
        self.assertEqual(out["positioning_pattern"], "liquidity_exit")
        self.assertFalse(out["squeeze_setup"])
        self.assertTrue(out["liquidity_exit"])
        self.assertEqual(out["pattern_label"], "Liquidity Exit")

    @patch("src.sentiment_superindex.data.cftc_patterns.check_cftc_freshness")
    def test_waiting_for_friday_when_stale(self, mock_fresh):
        mock_fresh.return_value = _FreshnessRow(
            stale=True,
            source_date="2026-07-22",
            expected_source_date="2026-07-29",
        )
        out = evaluate_cftc_positioning(40.0, 40.0, "2026-08-04")
        self.assertEqual(out["data_freshness"], "waiting_for_friday_release")
        self.assertEqual(out["status"], "PENDING_CFTC_CONFIRM")
        self.assertEqual(out["release_date"], "2026-07-25")
        # next_release must be in the FUTURE relative to as_of. It used to be computed as
        # expected_release + 3 days, which returns the Friday that has already passed
        # (2026-08-01 here, four days before the 2026-08-04 as-of) -- the tile then advertised
        # a "next release" date in the past. The overdue release is `expected_release`;
        # `next_release` is the next scheduled one.
        self.assertEqual(out["next_release"], "2026-08-08")
        self.assertGreater(
            pd.Timestamp(out["next_release"]), pd.Timestamp("2026-08-04")
        )
        self.assertEqual(out["expected_release"], "2026-07-29")


if __name__ == "__main__":
    unittest.main()


class TestPatternRuleLegs(unittest.TestCase):
    """A leg absent from the config must not be silently reinstated from a code default."""

    @patch("src.sentiment_superindex.data.cftc_patterns.check_cftc_freshness")
    def test_squeeze_ignores_rm_entirely(self, mock_fresh):
        mock_fresh.return_value = _FreshnessRow(
            stale=False, source_date="2026-07-29", expected_source_date="2026-07-29"
        )
        for rm_pctile in (1.0, 50.0, 99.0):
            out = evaluate_cftc_positioning(5.0, rm_pctile, "2026-08-04")
            self.assertEqual(out["positioning_pattern"], "squeeze", f"RM {rm_pctile} changed the verdict")

    @patch("src.sentiment_superindex.data.cftc_patterns.check_cftc_freshness")
    def test_boundaries(self, mock_fresh):
        mock_fresh.return_value = _FreshnessRow(
            stale=False, source_date="2026-07-29", expected_source_date="2026-07-29"
        )
        # "FM<10" is strict, "display >=80" is inclusive -- the cuts are written that way.
        self.assertEqual(evaluate_cftc_positioning(10.0, 50.0, "2026-08-04")["positioning_pattern"], None)
        self.assertEqual(evaluate_cftc_positioning(9.99, 50.0, "2026-08-04")["positioning_pattern"], "squeeze")
        self.assertEqual(evaluate_cftc_positioning(80.0, 50.0, "2026-08-04")["positioning_pattern"], "liquidity_exit")
        self.assertEqual(evaluate_cftc_positioning(79.99, 50.0, "2026-08-04")["positioning_pattern"], None)

    def test_pattern_rules_published_for_the_ui(self):
        from src.sentiment_superindex.data.cftc_patterns import pattern_rules

        rules = pattern_rules()
        self.assertEqual(rules["squeeze"], {"fm_pctile_max": 10.0})
        self.assertEqual(rules["liquidity_exit"], {"fm_pctile_min": 80.0})
