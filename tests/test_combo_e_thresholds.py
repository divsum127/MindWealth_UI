"""Combo E production thresholds + CFTC escalation alert."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.macro_intelligence.engine.combo_detector import (
    detect_named_combos,
    evaluate_combo_e_legs,
)


def _e_readings(
    cape: float = 35.0,
    nfci: float = -0.2,
    cftc_pctile: float = 90.0,
) -> dict:
    return {
        "CAPE": {"raw_value": cape, "unconditional_pctile": 95, "signal_tier": "EXTREME"},
        "NFCI": {"raw_value": nfci, "unconditional_pctile": 20, "signal_tier": "RARE"},
        "CFTC": {
            "raw_value": 100000,
            "unconditional_pctile": cftc_pctile,
            "pctile_rank_3yr": cftc_pctile,
            "signal_tier": "RARE",
        },
    }


class TestComboEThresholds(unittest.TestCase):
    def test_evaluate_legs_3_of_3(self) -> None:
        passed, pending = evaluate_combo_e_legs(_e_readings())
        self.assertEqual(passed, ["CAPE", "NFCI", "CFTC"])
        self.assertEqual(pending, [])

    def test_evaluate_legs_partial(self) -> None:
        passed, pending = evaluate_combo_e_legs(_e_readings(cape=20.0, nfci=-0.2, cftc_pctile=90))
        self.assertEqual(passed, ["NFCI", "CFTC"])
        self.assertIn("CAPE", pending)

    def test_old_gates_no_longer_fire_on_2_of_3(self) -> None:
        # CAPE 30 / NFCI -0.35 / CFTC 82 would have fired under old 2-of-3 (28/-0.3/80)
        # New gates need CAPE≥32, NFCI≤-0.15, CFTC≥85, all three
        readings = _e_readings(cape=30.0, nfci=-0.35, cftc_pctile=82.0)
        with patch(
            "src.macro_intelligence.engine.combo_detector._combo_e_escalation",
            return_value={"escalation_alert": False},
        ):
            fires = detect_named_combos("2026-01-02", readings)
        e = [f for f in fires if f.runic_combo == "E"]
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0].status, "WATCH")

    def test_3_of_3_confirmed(self) -> None:
        with patch(
            "src.macro_intelligence.engine.combo_detector._combo_e_escalation",
            return_value={"escalation_alert": False},
        ):
            fires = detect_named_combos("2026-01-02", _e_readings())
        e = [f for f in fires if f.runic_combo == "E"]
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0].status, "CONFIRMED_3_OF_3")
        self.assertEqual(e[0].macro_regime["confirmed_legs"], ["CAPE", "NFCI", "CFTC"])

    def test_escalation_status(self) -> None:
        with patch(
            "src.macro_intelligence.engine.combo_detector._combo_e_escalation",
            return_value={
                "escalation_alert": True,
                "cftc_pctile": 92.0,
                "cftc_pctile_prior": 85.0,
                "cftc_pctile_delta": 7.0,
            },
        ):
            fires = detect_named_combos("2026-01-02", _e_readings())
        e = [f for f in fires if f.runic_combo == "E"]
        self.assertEqual(e[0].status, "ESCALATION_ALERT")
        self.assertTrue(e[0].macro_regime["escalation_alert"])


if __name__ == "__main__":
    unittest.main()
