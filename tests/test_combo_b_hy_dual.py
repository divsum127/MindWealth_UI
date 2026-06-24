"""Combo B HY dual condition — abs floor + 80th percentile."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.combo_detector import (
    evaluate_combo_b_at_date,
    evaluate_combo_b_legs,
    _hy_oas_bps,
)


class TestComboBHyDual(unittest.TestCase):
    def test_hy_oas_bps_from_fred_percent(self) -> None:
        self.assertEqual(_hy_oas_bps(6.14), 614.0)
        self.assertEqual(_hy_oas_bps(2.74), 274.0)

    def test_dual_condition_required(self) -> None:
        self.assertTrue(
            evaluate_combo_b_at_date("2022-10-13", 33.6, 614.0, 8.0, vix_pctile=85, hy_pctile=85)
        )
        self.assertFalse(
            evaluate_combo_b_at_date("2022-10-13", 33.6, 614.0, 8.0, vix_pctile=85, hy_pctile=50)
        )
        self.assertFalse(
            evaluate_combo_b_at_date("2022-10-13", 33.6, 350.0, 8.0, vix_pctile=85, hy_pctile=85)
        )

    def test_watch_legs_exposed_for_partial_b(self) -> None:
        readings = {
            "VIX": {"raw_value": 18.7, "unconditional_pctile": 56.0},
            "HY": {"raw_value": 2.65, "unconditional_pctile": 3.0},
            "CFTC": {"raw_value": -500000, "unconditional_pctile": 0.6},
        }
        passed, pending = evaluate_combo_b_legs(readings)
        self.assertEqual(passed, ["CFTC"])
        self.assertEqual(pending, ["VIX", "HY"])


if __name__ == "__main__":
    unittest.main()
