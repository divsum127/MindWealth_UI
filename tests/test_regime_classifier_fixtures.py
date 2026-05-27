"""Regime classifier fixture dates from addendum A3."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.claude.regime_classifier import classify_regime


FIXTURES = [
    ("2022-10-13", "HIKING_LATE", "INVERTED", "SANCTIONS", "ELEVATED"),
    ("2020-03-23", "QE", "NORMAL", "PANDEMIC", "ELEVATED"),
    ("2020-06-29", "QE", "NORMAL", "PANDEMIC", "ELEVATED"),
    ("2015-12-16", "HIKING_EARLY", "NORMAL", "NEUTRAL", "ELEVATED"),
    ("2024-09-18", "CUTTING_EARLY", "STEEPENING", "NEUTRAL", "EXTREME"),
]


class TestRegimeFixtures(unittest.TestCase):
    def test_all_fixtures(self):
        for date, fed, curve, geo, val in FIXTURES:
            r = classify_regime(date, use_claude=False)
            self.assertEqual(r.fed_cycle, fed, msg=date)
            self.assertEqual(r.curve_regime, curve, msg=date)
            self.assertEqual(r.geo_overlay, geo, msg=date)
            self.assertEqual(r.val_regime, val, msg=date)


if __name__ == "__main__":
    unittest.main()
