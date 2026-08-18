"""Analog tables — per-combo fire history, matured horizons only.

Regression cover for the 2026-08-06 Runic page audit: all seven combos were serving the
same three fire dates with 6M mirroring 3M, 9M reading TBD, and CONTEXT / MAX DD / BOTTOM
TIMING blank throughout.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services import macro_service as msvc

COMBOS = ["A", "B", "C", "D", "E", "F", "G"]


class TestAnalogPerCombo(unittest.TestCase):
    def setUp(self) -> None:
        self.details = {letter: msvc.get_combo_detail(letter) for letter in COMBOS}

    def test_combos_do_not_share_a_fire_history(self) -> None:
        """Seven different trigger conditions cannot share a fire history."""
        signatures = {}
        for letter, detail in self.details.items():
            dates = tuple(a.get("date") for a in detail.get("analog_details") or [])
            if dates:
                signatures.setdefault(dates, []).append(letter)
        shared = {dates: letters for dates, letters in signatures.items() if len(letters) > 1}
        self.assertEqual(shared, {}, f"combos serving identical analog dates: {shared}")

    def test_every_returned_row_belongs_to_the_requested_combo(self) -> None:
        for letter, detail in self.details.items():
            for row in detail.get("analog_details") or []:
                self.assertEqual(row.get("combo"), letter)

    def test_six_month_is_not_a_copy_of_three_month(self) -> None:
        """6M was populated from the 3M field, identical in every row."""
        differing = 0
        for detail in self.details.values():
            for row in detail.get("analog_details") or []:
                m3, m6 = row.get("spx_3m_pct"), row.get("spx_6m_pct")
                if m3 is not None and m6 is not None and m3 != m6:
                    differing += 1
        self.assertGreater(differing, 0, "no row has a 6M distinct from its 3M")

    def test_unmatured_horizons_are_null_not_zero(self) -> None:
        """forward_returns stores 0.0 for horizons that have not elapsed."""
        today = datetime.now(UTC).date()
        for detail in self.details.values():
            for row in detail.get("analog_details") or []:
                fired = datetime.strptime(str(row["date"])[:10], "%Y-%m-%d").date()
                for horizon, field in (
                    ("spx_3m", "spx_3m_pct"),
                    ("spx_6m", "spx_6m_pct"),
                    ("spx_9m", "spx_9m_pct"),
                    ("spx_12m", "spx_12m_pct"),
                ):
                    matured = fired + timedelta(days=msvc._HORIZON_DAYS[horizon]) <= today
                    if not matured:
                        self.assertIsNone(
                            row.get(field),
                            f"{row['date']} {field} reported before the window closed",
                        )

    def test_low_episode_combo_is_flagged(self) -> None:
        """Combo C has 3 matured episodes — below the 5-episode floor."""
        c = self.details["C"]
        self.assertTrue(c["insufficient_history"])
        self.assertLess(c["matured_episodes"], c["min_matured_episodes"])

    def test_combo_without_fires_returns_empty_not_fabricated(self) -> None:
        g = self.details["G"]
        self.assertEqual(g["analog_details"], [])
        self.assertEqual(g["matured_episodes"], 0)
        self.assertTrue(g["insufficient_history"])

    def test_matured_rows_carry_drawdown_and_bottom_timing(self) -> None:
        """MAX DD / BOTTOM TIMING are why the tab exists; they read blank throughout."""
        c_rows = self.details["C"]["analog_details"]
        self.assertTrue(c_rows, "expected matured Combo C fires")
        gfc = next((r for r in c_rows if str(r["date"]).startswith("2008")), None)
        self.assertIsNotNone(gfc, "expected the 2008 Combo C fire")
        self.assertIsNotNone(gfc["max_dd_pct"])
        self.assertLess(gfc["max_dd_pct"], -20.0, "2008 window should show a deep drawdown")
        self.assertGreater(gfc["bottom_timing_days"], 0)

    def test_drawdown_is_peak_to_trough(self) -> None:
        """A window that only rose still has a peak-to-trough drawdown, not 0%."""
        stats = msvc._analog_drawdown_stats(["2020-07-24"])
        self.assertIn("2020-07-24", stats)
        self.assertLess(stats["2020-07-24"]["max_dd_pct"], 0.0)

    def test_primary_horizon_is_schema_validated(self) -> None:
        """The horizon is interpolated into SQL — it must never leave the allowlist."""
        self.assertIn(msvc._combo_primary_horizon("C"), msvc._ALLOWED_HORIZONS)
        self.assertEqual(msvc._combo_primary_horizon("NOT_A_COMBO"), "spx_3m")


if __name__ == "__main__":
    unittest.main()
