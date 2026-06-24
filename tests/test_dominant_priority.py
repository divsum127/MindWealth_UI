"""Dominant combo PRIORITY ordering."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.dominant import determine_dominant_combo

# Priority order: C(100) > B(90) > F(80) > E(70) > D(60) > G(50) > A(40)


class TestDominantPriority(unittest.TestCase):
    def test_c_beats_f(self) -> None:
        active = [
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 8},
            {"combo": "C", "status": "ACTIVE", "duration_weeks": 11},
        ]
        dom, _, brave = determine_dominant_combo(active)
        self.assertEqual(dom, "C")
        self.assertEqual(brave, "TACTICAL_TIGHT_MONEY_STRATEGIC_EASY_MONEY")

    def test_b_beats_g(self) -> None:
        active = [
            {"combo": "G", "status": "ACTIVE"},
            {"combo": "B", "status": "ACTIVE"},
        ]
        dom, _, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "B")

    def test_f_beats_e(self) -> None:
        active = [
            {"combo": "E", "status": "CONFIRMED"},
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 10},
        ]
        dom, _, brave = determine_dominant_combo(active)
        self.assertEqual(dom, "F")
        self.assertEqual(brave, "TACTICAL_EASY_MONEY")

    def test_e_beats_d(self) -> None:
        active = [
            {"combo": "D", "status": "ACTIVE"},
            {"combo": "E", "status": "CONFIRMED"},
        ]
        dom, _, brave = determine_dominant_combo(active)
        self.assertEqual(dom, "E")
        self.assertEqual(brave, "STRATEGIC_CAUTIOUS")

    def test_d_beats_g(self) -> None:
        active = [
            {"combo": "G", "status": "ACTIVE"},
            {"combo": "D", "status": "ACTIVE"},
        ]
        dom, _, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "D")

    def test_b_beats_f(self) -> None:
        active = [
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 5},
            {"combo": "B", "status": "ACTIVE"},
        ]
        dom, _, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "B")

    def test_runner_up_is_second_priority(self) -> None:
        active = [
            {"combo": "D", "status": "ACTIVE"},
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 1},
            {"combo": "E", "status": "CONFIRMED"},
        ]
        dom, reason, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "F")
        self.assertIn("Outranks Combo E", reason)
        self.assertNotIn("Outranks Combo D", reason)


if __name__ == "__main__":
    unittest.main()
