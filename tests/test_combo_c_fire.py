"""Combo C fire condition — HOT CPI surprise required."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.combo_detector import detect_named_combos


def _readings(wti: float, cpi_surprise: float, walcl_mom: float = 0.1) -> dict:
    return {
        "WTI": {"raw_value": wti, "direction": "UP", "signal_tier": "EXTREME"},
        "CPI": {"raw_value": cpi_surprise, "direction": "UP", "signal_tier": "RARE"},
        "WALCL": {"raw_value": walcl_mom, "direction": None, "signal_tier": "NORMAL"},
    }


class TestComboCFire(unittest.TestCase):
    @patch("src.macro_intelligence.engine.combo_detector._combo_c_still_active", return_value=False)
    def test_hot_surprise_fires(self, _mock: object) -> None:
        fires = detect_named_combos("2026-04-01", _readings(wti=12.0, cpi_surprise=0.25))
        c_fires = [f for f in fires if f.runic_combo == "C"]
        self.assertEqual(len(c_fires), 1)

    @patch("src.macro_intelligence.engine.combo_detector._combo_c_still_active", return_value=False)
    def test_cold_surprise_does_not_fire(self, _mock: object) -> None:
        fires = detect_named_combos("2026-04-01", _readings(wti=12.0, cpi_surprise=-0.3))
        c_fires = [f for f in fires if f.runic_combo == "C"]
        self.assertEqual(len(c_fires), 0)


if __name__ == "__main__":
    unittest.main()
