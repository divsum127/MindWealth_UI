"""Combo D production thresholds — BEST PRODUCTION SCORE 2-of-3."""

from __future__ import annotations

import unittest

from src.macro_intelligence.engine.combo_detector import (
    detect_named_combos,
    evaluate_combo_d_legs,
)


def _d_readings(
    vxts: float = 1.20,
    vix: float = 12.0,
    cftc_pctile: float = 96.0,
) -> dict:
    return {
        "VXTS": {"raw_value": vxts, "unconditional_pctile": 80, "signal_tier": "RARE", "direction": "UP"},
        "VIX": {"raw_value": vix, "unconditional_pctile": 20, "signal_tier": "NORMAL", "direction": "DOWN"},
        "CFTC": {
            "raw_value": 200000,
            "unconditional_pctile": cftc_pctile,
            "pctile_rank_3yr": cftc_pctile,
            "signal_tier": "RARE",
            "direction": "UP",
        },
    }


class TestComboDThresholds(unittest.TestCase):
    def test_evaluate_legs_3_of_3(self) -> None:
        passed, pending = evaluate_combo_d_legs(_d_readings())
        self.assertEqual(passed, ["VXTS", "VIX", "CFTC"])
        self.assertEqual(pending, [])

    def test_evaluate_legs_2_of_3(self) -> None:
        # VIX above max → pending; VXTS+CFTC still fire ACTIVE under 2-of-3
        passed, pending = evaluate_combo_d_legs(_d_readings(vix=20.0))
        self.assertEqual(passed, ["VXTS", "CFTC"])
        self.assertEqual(pending, ["VIX"])

    def test_legacy_gates_too_loose_do_not_fire(self) -> None:
        # Old CONFIG-style: VXTS 1.12, VIX 17, CFTC 86 — fails new gates
        readings = _d_readings(vxts=1.12, vix=17.0, cftc_pctile=86.0)
        fires = detect_named_combos("2026-01-02", readings)
        d = [f for f in fires if f.runic_combo == "D"]
        self.assertEqual(len(d), 0)

    def test_2_of_3_active(self) -> None:
        fires = detect_named_combos("2026-01-02", _d_readings(vix=20.0))
        d = [f for f in fires if f.runic_combo == "D"]
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0].status, "ACTIVE")
        self.assertEqual(d[0].macro_regime["confirmed_legs"], ["VXTS", "CFTC"])

    def test_1_of_3_watch(self) -> None:
        fires = detect_named_combos("2026-01-02", _d_readings(vxts=1.05, vix=20.0, cftc_pctile=96.0))
        d = [f for f in fires if f.runic_combo == "D"]
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0].status, "WATCH")
        self.assertEqual(d[0].macro_regime["confirmed_legs"], ["CFTC"])

    def test_vix_inclusive_max(self) -> None:
        # VIX == 13 should pass (≤ gate)
        passed, _ = evaluate_combo_d_legs(_d_readings(vix=13.0))
        self.assertIn("VIX", passed)


if __name__ == "__main__":
    unittest.main()
