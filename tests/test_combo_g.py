"""Combo G requires HY 4wk widening."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.combo_detector import detect_named_combos


class TestComboG(unittest.TestCase):
    def test_g_fires_when_hy_widens(self) -> None:
        readings = {
            "VXTS": {"raw_value": 0.95, "signal_tier": "NORMAL"},
            "VIX": {"raw_value": 15, "signal_tier": "NORMAL"},
            "HY": {"raw_value": 400, "signal_tier": "NORMAL", "direction": "UP"},
            "NFCI": {"raw_value": 0, "signal_tier": "NORMAL"},
            "WALCL": {"raw_value": 0, "signal_tier": "NORMAL"},
            "CNH": {"raw_value": 0, "signal_tier": "NORMAL"},
            "WTI": {"raw_value": 0, "signal_tier": "NORMAL"},
            "CPI": {"raw_value": 0, "signal_tier": "NORMAL"},
            "CAPE": {"raw_value": 20, "signal_tier": "NORMAL"},
            "CURVE": {"raw_value": 0, "signal_tier": "NORMAL"},
            "CFTC": {"raw_value": 0, "unconditional_pctile": 50, "signal_tier": "NORMAL"},
        }
        with patch(
            "src.macro_intelligence.engine.combo_detector._hy_4wk_change_bps",
            return_value=35.0,
        ):
            fires = detect_named_combos("2024-01-01", readings)
        g = [f for f in fires if f.runic_combo == "G"]
        self.assertEqual(len(g), 1)

    def test_g_skips_without_hy_widen(self) -> None:
        readings = {
            "VXTS": {"raw_value": 0.95, "signal_tier": "NORMAL"},
            "VIX": {"raw_value": 15, "signal_tier": "NORMAL"},
            "HY": {"raw_value": 300, "signal_tier": "NORMAL"},
        }
        with patch(
            "src.macro_intelligence.engine.combo_detector._hy_4wk_change_bps",
            return_value=10.0,
        ):
            fires = detect_named_combos("2024-01-01", readings)
        self.assertEqual([f for f in fires if f.runic_combo == "G"], [])


if __name__ == "__main__":
    unittest.main()
