"""Combo C cancel probability — sigma sourcing, banked Fridays, 4wk ROC barrier.

Regression cover for Rohit's 6 Aug audit: P(cancel) was byte-identical across three days
and pointed the wrong way, reading 2% while the WTI leg was already passing with 1 of 4
Fridays banked.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine import combo_cancel_probability as ccp

# A flat-to-falling oil tape: the trailing 4wk ROC is negative, so the cancel leg passes.
FLAT_HISTORY = [89.31, 84.67, 78.18, 82.40, 82.42]
SIGMA = 0.50


class TestBankedFridays(unittest.TestCase):
    def test_probability_rises_as_fridays_bank(self) -> None:
        probs = [
            ccp.combo_cancel_probability_wti(
                82.42, vol_annual=SIGMA, weeks_banked=banked, weekly_history=FLAT_HISTORY
            )["monte_carlo_prob_all_4"]
            for banked in range(4)
        ]
        self.assertEqual(probs, sorted(probs), f"not monotonic in banked weeks: {probs}")
        self.assertGreater(probs[3], probs[0])

    def test_barrier_count_drops_with_banked_weeks(self) -> None:
        for banked in range(5):
            result = ccp.combo_cancel_probability_wti(
                82.42, vol_annual=SIGMA, weeks_banked=banked, weekly_history=FLAT_HISTORY
            )
            self.assertEqual(result["weeks_remaining"], max(0, 4 - banked))

    def test_all_four_banked_is_certain(self) -> None:
        result = ccp.combo_cancel_probability_wti(
            82.42, vol_annual=SIGMA, weeks_banked=4, weekly_history=FLAT_HISTORY
        )
        self.assertEqual(result["monte_carlo_prob_all_4"], 1.0)
        self.assertEqual(result["weeks_remaining"], 0)

    def test_banked_weeks_clamped_to_requirement(self) -> None:
        result = ccp.combo_cancel_probability_wti(
            82.42, vol_annual=SIGMA, weeks_banked=99, weekly_history=FLAT_HISTORY
        )
        self.assertEqual(result["weeks_banked"], 4)


class TestBarrierBasis(unittest.TestCase):
    def test_passing_leg_gives_a_material_probability(self) -> None:
        """A tape whose 4wk ROC is already negative must not read as near-impossible."""
        roc = FLAT_HISTORY[-1] / FLAT_HISTORY[0] - 1.0
        self.assertLess(roc, 0.05, "fixture should already pass the +5% gate")
        result = ccp.combo_cancel_probability_wti(
            FLAT_HISTORY[-1], vol_annual=SIGMA, weeks_banked=1, weekly_history=FLAT_HISTORY
        )
        self.assertGreater(result["monte_carlo_prob_all_4"], 0.20)
        self.assertEqual(result["barrier_basis"], "trailing_4wk_roc")

    def test_recent_spike_lowers_probability(self) -> None:
        """A tape that just rallied hard is closer to breaching the +5% gate."""
        spiking = [70.0, 72.0, 75.0, 79.0, 84.0]
        flat = ccp.combo_cancel_probability_wti(
            82.42, vol_annual=SIGMA, weeks_banked=0, weekly_history=FLAT_HISTORY
        )["monte_carlo_prob_all_4"]
        spike = ccp.combo_cancel_probability_wti(
            84.0, vol_annual=SIGMA, weeks_banked=0, weekly_history=spiking
        )["monte_carlo_prob_all_4"]
        self.assertLess(spike, flat)


class TestSigmaSourcing(unittest.TestCase):
    def test_explicit_sigma_is_labelled(self) -> None:
        result = ccp.combo_cancel_probability_wti(
            82.42, vol_annual=0.42, weekly_history=FLAT_HISTORY
        )
        self.assertEqual(result["sigma"], 0.42)
        self.assertEqual(result["sigma_source"], "explicit_argument")

    def test_resolved_sigma_declares_its_source(self) -> None:
        info = ccp.wti_sigma()
        self.assertIn(info["sigma_source"], {"ovx_implied", "realised_60d", "config_default"})
        self.assertGreater(info["sigma"], 0.0)
        self.assertLess(info["sigma"], 5.0)

    def test_output_is_deterministic_for_the_same_inputs(self) -> None:
        args = dict(vol_annual=SIGMA, weeks_banked=1, weekly_history=FLAT_HISTORY)
        first = ccp.combo_cancel_probability_wti(82.42, **args)
        second = ccp.combo_cancel_probability_wti(82.42, **args)
        self.assertEqual(
            first["monte_carlo_prob_all_4"], second["monte_carlo_prob_all_4"]
        )

    def test_output_moves_when_the_tape_moves(self) -> None:
        """Byte-identical output across days was the original symptom."""
        a = ccp.combo_cancel_probability_wti(
            82.42, vol_annual=SIGMA, weeks_banked=1, weekly_history=FLAT_HISTORY
        )["monte_carlo_prob_all_4"]
        b = ccp.combo_cancel_probability_wti(
            88.00, vol_annual=SIGMA, weeks_banked=1, weekly_history=[*FLAT_HISTORY[:-1], 88.0]
        )["monte_carlo_prob_all_4"]
        self.assertNotEqual(a, b)


class TestCpiLeg(unittest.TestCase):
    def test_print_count_tracks_the_remaining_window(self) -> None:
        self.assertEqual(ccp.cpi_prints_in_window(0), 0)
        self.assertEqual(ccp.cpi_prints_in_window(3), 1)
        self.assertEqual(ccp.cpi_prints_in_window(4), 1)
        self.assertEqual(ccp.cpi_prints_in_window(8), 2)

    def test_rate_is_derived_with_a_sample_size(self) -> None:
        info = ccp.cpi_not_hot_rate()
        self.assertGreaterEqual(info["rate"], 0.0)
        self.assertLessEqual(info["rate"], 1.0)
        self.assertIsNotNone(info["n_obs"])
        self.assertIn("source", info)

    def test_total_keeps_the_original_output_contract(self) -> None:
        mc = ccp.combo_cancel_probability_wti(
            82.42, vol_annual=SIGMA, weeks_banked=1, weekly_history=FLAT_HISTORY
        )
        total = ccp.combo_c_total_cancel_prob(mc, cpi_not_hot_rate=0.5)
        for key in ("wti_leg", "combined_cancel_prob", "cpi_leg_prob"):
            self.assertIn(key, total)
        self.assertAlmostEqual(
            total["combined_cancel_prob"],
            mc["monte_carlo_prob_all_4"] * total["cpi_leg_prob"],
            places=9,
        )

    def test_cpi_leg_is_not_squared_for_a_short_window(self) -> None:
        """Three Fridays left means one CPI print, not two."""
        mc = ccp.combo_cancel_probability_wti(
            82.42, vol_annual=SIGMA, weeks_banked=1, weekly_history=FLAT_HISTORY
        )
        total = ccp.combo_c_total_cancel_prob(mc, cpi_not_hot_rate=0.5)
        self.assertEqual(total["cpi_prints_in_window"], 1)
        self.assertAlmostEqual(total["cpi_leg_prob"], 0.5, places=9)


if __name__ == "__main__":
    unittest.main()
