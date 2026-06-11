"""Combo hit-rate metadata — horizons and direction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.combo_metadata import (
    combo_bullish,
    combo_primary_horizon,
    combo_show_hit_rate,
    horizon_display_label,
)


class TestComboMetadata(unittest.TestCase):
    def test_combo_e_bearish_12m(self) -> None:
        self.assertFalse(combo_bullish("E"))
        self.assertEqual(combo_primary_horizon("E"), "spx_12m")
        self.assertEqual(horizon_display_label("spx_12m"), "12M")

    def test_combo_g_no_hit_rate(self) -> None:
        self.assertIsNone(combo_bullish("G"))
        self.assertFalse(combo_show_hit_rate("G"))

    def test_combo_b_bullish_3m(self) -> None:
        self.assertTrue(combo_bullish("B"))
        self.assertEqual(combo_primary_horizon("B"), "spx_3m")

    def test_combo_d_5d_horizon(self) -> None:
        self.assertEqual(combo_primary_horizon("D"), "spx_1w")
        self.assertEqual(horizon_display_label("spx_1w"), "5D")


if __name__ == "__main__":
    unittest.main()
