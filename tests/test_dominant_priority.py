"""Dominant combo PRIORITY ordering."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.dominant import determine_dominant_combo


class TestDominantPriority(unittest.TestCase):
    def test_c_beats_f(self) -> None:
        active = [
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 8},
            {"combo": "C", "status": "ACTIVE", "duration_weeks": 11},
        ]
        dom, _, brave = determine_dominant_combo(active)
        self.assertEqual(dom, "C")
        self.assertIn("TACTICAL_FEARFUL", brave)

    def test_b_higher_than_g(self) -> None:
        active = [
            {"combo": "G", "status": "ACTIVE"},
            {"combo": "B", "status": "ACTIVE"},
        ]
        dom, _, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "B")


if __name__ == "__main__":
    unittest.main()
