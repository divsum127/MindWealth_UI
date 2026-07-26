"""FFR-based fed_cycle labels for spec fixture dates."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.fed_cycle import build_fed_cycle_series, clear_fed_cycle_cache, fed_cycle_at_date

FED_FIXTURES = [
    ("2022-10-13", "HIKING_LATE"),
    ("2020-03-23", "QE"),
    ("2020-06-29", "QE"),
    ("2015-12-16", "HIKING_EARLY"),
    ("2024-09-18", "CUTTING_EARLY"),
]


class TestFedCycleFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        clear_fed_cycle_cache()
        cls._series = build_fed_cycle_series(force=True)

    def test_fed_cycle_at_date(self):
        for date, expected in FED_FIXTURES:
            label, _ = fed_cycle_at_date(date)
            self.assertEqual(label, expected, msg=f"{date}: got {label}")

    def test_series_non_empty(self):
        self.assertGreater(len(self._series), 500)

    def test_pause_does_not_resurrect_stale_hike_or_cut_label(self):
        """T-01 regression (2026-06-06 audit): fed_cycle_at_date() must report PAUSING once the
        Fed has actually paused, not carry forward the last completed cycle's label
        (e.g. CUTTING_LATE) via the historical-rescan fallback."""
        series = self._series
        pause_dates = [d for d, v in series.items() if v == "PAUSING"]
        self.assertTrue(pause_dates, "fixture series has no PAUSING weeks to test against")
        # Well into an established pause (skip the very first pause week, which can still fall
        # back to the rescan if the series itself hasn't caught up yet).
        probe_date = pause_dates[len(pause_dates) // 2].strftime("%Y-%m-%d")
        label, source = fed_cycle_at_date(probe_date)
        self.assertEqual(label, "PAUSING", msg=f"{probe_date}: got {label} (source={source})")


if __name__ == "__main__":
    unittest.main()
