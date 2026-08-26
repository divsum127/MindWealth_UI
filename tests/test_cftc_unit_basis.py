"""The 2023-05-02 CFTC unit seam: restatement and the standing break test.

CFTC redefined the "S&P 500 Consolidated" line on 2023-05-02 -- before it was big-contract
($250) equivalents with micro excluded, after it is E-mini ($50) equivalents with micro
included. The published series therefore scales ~5x in one week and no rolling window spanning
that date is rankable. Fixture rows are the real CFTC prints for the two weeks either side.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data.cftc_pull import (  # noqa: E402
    _emini_equivalent_series,
    _positioning_series,
    _stitch_legacy_consolidated_net,
    detect_unit_break,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cftc" / "tff_unit_break_sample.csv"
PLAIN_FIXTURE = Path(__file__).parent / "fixtures" / "cftc" / "tff_sample.csv"
PRE = pd.Timestamp("2023-04-25")
POST = pd.Timestamp("2023-05-02")


class TestCftcUnitBasis(unittest.TestCase):
    def setUp(self):
        self.df = pd.read_csv(FIXTURE)

    def test_published_consolidated_line_carries_the_seam(self):
        """Baseline: the seam is in the source, not introduced by our parsing."""
        fm = _stitch_legacy_consolidated_net(self.df, asset_manager=False)
        self.assertAlmostEqual(fm.loc[PRE], -95014.0)
        self.assertAlmostEqual(fm.loc[POST], -457123.0)
        self.assertGreater(abs(fm.loc[POST] / fm.loc[PRE]), 4.5)

    def test_restated_series_is_continuous_across_the_seam(self):
        fm = _emini_equivalent_series(self.df, asset_manager=False)
        # E-mini net + micro net / 10, both weeks in the same unit.
        self.assertAlmostEqual(fm.loc[PRE], (142442 - 617508) + (142555 - 76601) / 10)
        self.assertAlmostEqual(fm.loc[POST], (134979 - 602843) + (168099 - 60691) / 10)
        self.assertLess(abs(fm.loc[POST] / fm.loc[PRE]), 1.1)

    def test_restated_matches_published_consolidated_after_the_change(self):
        """Post-2023 the restatement must reproduce CFTC's own number, not merely be smooth."""
        for asset_manager in (False, True):
            restated = _emini_equivalent_series(self.df, asset_manager=asset_manager)
            published = _stitch_legacy_consolidated_net(self.df, asset_manager=asset_manager)
            self.assertLessEqual(abs(restated.loc[POST] - published.loc[POST]), 1.0)

    def test_pre_change_restatement_is_five_times_the_published_line(self):
        """Big-contract equivalents -> E-mini equivalents is a factor of five, plus micro."""
        rm = _emini_equivalent_series(self.df, asset_manager=True)
        published = _stitch_legacy_consolidated_net(self.df, asset_manager=True)
        ratio = rm.loc[PRE] / published.loc[PRE]
        self.assertGreater(ratio, 4.9)
        self.assertLess(ratio, 5.2)

    def test_open_interest_uses_the_same_basis(self):
        oi = _emini_equivalent_series(self.df, open_interest=True)
        self.assertAlmostEqual(oi.loc[POST], 2276183 + 284500 / 10)
        self.assertLess(oi.loc[POST] / oi.loc[PRE], 1.1)

    def test_detect_unit_break_flags_the_published_series(self):
        published = pd.DataFrame(
            {
                "open_interest": [453159.0, 2304633.0],
                "fm_net": [-95014.0, -457123.0],
                "rm_net": [116895.0, 594746.0],
            },
            index=[PRE, POST],
        )
        breaks = detect_unit_break(published)
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0]["date"], "2023-05-02")
        self.assertGreater(breaks[0]["common_factor"], 4.5)

    def test_detect_unit_break_ignores_a_large_but_disagreeing_move(self):
        """Positioning can triple in a week; open interest does not follow it tick for tick."""
        positioning = pd.DataFrame(
            {
                "open_interest": [2265266.0, 2298954.0],
                "fm_net": [-90000.0, -280000.0],
                "rm_net": [537506.0, 540000.0],
            },
            index=[PRE, POST],
        )
        self.assertEqual(detect_unit_break(positioning), [])

    def test_restated_series_has_no_break(self):
        restated = pd.DataFrame(
            {
                "open_interest": _emini_equivalent_series(self.df, open_interest=True),
                "fm_net": _emini_equivalent_series(self.df, asset_manager=False),
                "rm_net": _emini_equivalent_series(self.df, asset_manager=True),
            }
        )
        self.assertEqual(detect_unit_break(restated), [])

    def test_falls_back_to_consolidated_when_component_lines_are_absent(self):
        """Older fixtures and any file holding only the Consolidated line must still parse."""
        plain = pd.read_csv(PLAIN_FIXTURE)
        self.assertTrue(_emini_equivalent_series(plain, asset_manager=False).empty)
        fm = _positioning_series(plain, asset_manager=False)
        self.assertFalse(fm.empty)
        self.assertAlmostEqual(fm.loc[pd.Timestamp("2022-10-11")], -60000.0)


if __name__ == "__main__":
    unittest.main()
