"""Dominant combo PRIORITY ordering."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.dominant import (
    determine_dominant_combo,
    is_validated_combo,
    priority_ranking,
)

# Priority order after Rohit's 2026-08-06 sign-off:
#   B(100) > C(90) > F(80) > E(70) > D(60) > G(50) > A(40)
# plus a general low-n rule: any combo with fewer than 5 matured episodes ranks BELOW
# every validated combo, whatever its PRIORITY number. C currently has n=3, so C sorts
# below F/E/D/A in practice even though its PRIORITY is 90.


class TestDominantPriority(unittest.TestCase):
    def test_b_beats_c_on_co_fire(self) -> None:
        """The oil-shock case: WTI +10% AND VIX>25 AND HY>400bps AND CFTC<15th together.

        C's bearish call must not suppress the capitulation buy at the bottom.
        """
        active = [
            {"combo": "C", "status": "ACTIVE", "duration_weeks": 11},
            {"combo": "B", "status": "ACTIVE"},
        ]
        dom, _, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "B")

    def test_low_n_combo_demoted_below_validated(self) -> None:
        """C (n=3) sits below F even though C's PRIORITY number is higher."""
        self.assertFalse(is_validated_combo("C"))
        self.assertTrue(is_validated_combo("F"))
        active = [
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 8},
            {"combo": "C", "status": "ACTIVE", "duration_weeks": 11},
        ]
        dom, reason, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "F")
        self.assertIn("below every validated combo", reason)

    def test_low_n_combo_still_dominant_when_alone(self) -> None:
        """Demotion is relative — C alone is still the dominant combo."""
        dom, _, brave = determine_dominant_combo([{"combo": "C", "status": "ACTIVE", "duration_weeks": 11}])
        self.assertEqual(dom, "C")
        self.assertEqual(brave, "NEUTRAL")

    def test_c_beats_f_when_both_validated(self) -> None:
        """PRIORITY still decides between two combos on the same validation footing."""
        active = [
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 8},
            {"combo": "C", "status": "ACTIVE", "duration_weeks": 11},
        ]
        with mock.patch(
            "src.macro_intelligence.engine.dominant.is_validated_combo", return_value=True
        ):
            dom, _, brave = determine_dominant_combo(active)
        self.assertEqual(dom, "C")
        self.assertEqual(brave, "TACTICAL_TIGHT_MONEY_STRATEGIC_EASY_MONEY")

    def test_priority_ranking_puts_b_first_and_low_n_last(self) -> None:
        rows = priority_ranking()
        self.assertEqual(rows[0]["combo"], "B")
        self.assertEqual(rows[0]["position"], 1)
        demoted = [r["combo"] for r in rows if r["demoted_for_low_n"]]
        self.assertIn("C", demoted)
        # Every demoted combo sorts after every validated one.
        positions = {r["combo"]: r["position"] for r in rows}
        validated = [r["combo"] for r in rows if not r["demoted_for_low_n"]]
        self.assertTrue(all(positions[d] > positions[v] for d in demoted for v in validated))

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
