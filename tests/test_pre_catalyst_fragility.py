"""Tests for pre-catalyst fragility scoring."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.pre_catalyst_fragility import (
    FRAGILITY_LABEL,
    count_near_threshold,
    compute_pre_catalyst_fragility,
    is_near_threshold,
)


def _reading(pctile: float) -> dict:
    return {"unconditional_pctile": pctile, "signal_tier": "NORMAL"}


class TestPreCatalystFragility(unittest.TestCase):
    def test_is_near_threshold_high_band(self) -> None:
        self.assertTrue(is_near_threshold(65.0))
        self.assertTrue(is_near_threshold(79.0))
        self.assertFalse(is_near_threshold(80.0))
        self.assertFalse(is_near_threshold(50.0))

    def test_is_near_threshold_low_band(self) -> None:
        self.assertTrue(is_near_threshold(25.0))
        self.assertFalse(is_near_threshold(15.0))

    def test_count_near_threshold(self) -> None:
        readings = {
            "NFCI": _reading(70),
            "HY": _reading(50),
            "VIX": _reading(75),
            "CNH": _reading(30),
            "WALCL": _reading(65),
        }
        count, vars_near = count_near_threshold(readings)
        self.assertEqual(count, 4)
        self.assertEqual(set(vars_near), {"NFCI", "VIX", "WALCL", "CNH"})

    def test_compute_fragility_high_when_four_plus(self) -> None:
        from unittest.mock import patch

        readings = {f"V{i}": _reading(70) for i in range(12)}
        readings.update(
            {
                "NFCI": _reading(70),
                "HY": _reading(72),
                "VIX": _reading(68),
                "CNH": _reading(71),
            }
        )
        with patch(
            "src.macro_intelligence.engine.pre_catalyst_fragility.get_upcoming_event",
            return_value={"type": "FOMC", "date": "2026-07-01", "days_to_event": 3},
        ):
            out = compute_pre_catalyst_fragility("2026-06-28", readings)
        self.assertTrue(out["active"])
        self.assertEqual(out["fragility_score"], FRAGILITY_LABEL)
        self.assertGreaterEqual(out["near_threshold_count"], 4)

    def test_compute_fragility_null_when_few_vars(self) -> None:
        from unittest.mock import patch

        readings = {"NFCI": _reading(70), "HY": _reading(50)}
        with patch(
            "src.macro_intelligence.engine.pre_catalyst_fragility.get_upcoming_event",
            return_value={"type": "NFP", "date": "2026-07-04", "days_to_event": 2},
        ):
            out = compute_pre_catalyst_fragility("2026-07-02", readings)
        self.assertTrue(out["active"])
        self.assertIsNone(out["fragility_score"])


if __name__ == "__main__":
    unittest.main()
