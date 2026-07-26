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
    combo_fed_cycle_slice_stats,
    combo_hit_rate_stats,
    combo_primary_horizon,
    combo_show_hit_rate,
    format_hit_rate_display,
    horizon_display_label,
    min_episodes_for_hit_rate,
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

    def test_combo_c_min_episodes_config(self) -> None:
        self.assertEqual(min_episodes_for_hit_rate("C"), 5)

    def test_format_hit_rate_insufficient_episodes(self) -> None:
        stats = {
            "show_hit_rate": True,
            "insufficient_episodes": True,
            "n_obs_primary": 4,
            "min_episodes_required": 5,
        }
        hr, avg = format_hit_rate_display(stats)
        self.assertEqual(hr, "insufficient episodes")
        self.assertEqual(avg, "—")

    def test_combo_c_hit_rate_stats_insufficient_when_few_fires(self) -> None:
        from unittest.mock import patch

        with patch(
            "src.macro_intelligence.engine.combo_metadata.raw_hit_rate",
            return_value={"hit_rate": 0.0, "n_obs": 4, "avg_return": 17.8},
        ):
            stats = combo_hit_rate_stats("C")
        self.assertTrue(stats.get("insufficient_episodes"))
        self.assertIsNone(stats.get("hit_rate_primary"))
        self.assertEqual(stats.get("n_obs_primary"), 4)
        hr, avg = format_hit_rate_display(stats)
        self.assertEqual(hr, "insufficient episodes")

    def test_combo_d_fed_cycle_slices_qe_usable(self) -> None:
        stats = combo_fed_cycle_slice_stats("D")
        self.assertIsNotNone(stats)
        assert stats is not None
        self.assertEqual(stats["min_episodes"], 9)
        by_regime = {s["fed_cycle"]: s for s in stats["slices"]}
        self.assertEqual(by_regime["CUTTING_LATE"]["verdict"], "USE")
        self.assertEqual(by_regime["HIKING_LATE"]["verdict"], "USE")
        qe = by_regime["QE"]
        self.assertEqual(qe["verdict"], "USE")
        qe_1w = qe["horizons"]["spx_1w"]
        self.assertEqual(qe_1w["n"], 9)
        self.assertAlmostEqual(qe_1w["hit_rate"], 0.4444, places=4)
        self.assertAlmostEqual(qe_1w["avg_return"], 0.649, places=3)
        self.assertEqual(qe_1w["label"], "5D")

    def test_combo_b_no_fed_cycle_slices(self) -> None:
        self.assertIsNone(combo_fed_cycle_slice_stats("B"))


if __name__ == "__main__":
    unittest.main()
