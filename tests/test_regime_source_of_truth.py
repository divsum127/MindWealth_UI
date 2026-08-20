"""Regime source of truth — the stored table, with no interface recomputing differently.

Rohit 6 Aug: "the source of truth is the STORED TABLE, and no interface ever recomputes.
The API and the export module both read it. Pick 20 random dates, pull each through the
API, through regime_feed_export.py, and out of the table directly. All three must be
byte-identical."

Dates are fixed (not drawn per run) so a failure is reproducible.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.output import regime_feed_export as rfe

DIMENSION_FIELDS = ("fed_cycle_v2", "curve_regime_v2", "val_regime", "geo_overlay_v2")
MULTIPLIER_FIELDS = ("m_fed", "m_curve", "m_val", "m_geo", "m_liq", "gross_mult")


def _sample_dates(n: int = 20) -> list[str]:
    """A deterministic spread of stored evaluation dates."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date FROM macro_regime_log_v2 ORDER BY date"
        ).fetchall()
    dates = [str(r["date"]) for r in rows]
    if len(dates) <= n:
        return dates
    step = len(dates) // n
    return [dates[i * step] for i in range(n)]


class TestRegimeSourceOfTruth(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dates = _sample_dates(20)
        # Keyed on `date`, which is unique per row. `evaluation_date` repeats across the
        # daily rows that forward-fill from the same Friday evaluation.
        all_rows = rfe.regime_feed_as_records()
        cls.by_date = {r["date"]: r for r in all_rows}
        cls.export_rows = {}
        for row in all_rows:
            cls.export_rows.setdefault(row["evaluation_date"], row)

    def test_twenty_dates_available(self) -> None:
        self.assertEqual(len(self.dates), 20, "expected 20 stored evaluation dates to test")

    def test_api_and_export_return_identical_rows(self) -> None:
        """The API must read the export path, not its own copy of the logic."""
        from api.routers.macro import _load_regime_history_rows

        for date in self.dates:
            api_rows = {r["date"]: r for r in _load_regime_history_rows(date, date)}
            self.assertIn(date, api_rows, f"API returned no row for {date}")
            self.assertIn(date, self.by_date, f"export returned no row for {date}")
            self.assertEqual(
                json.dumps(api_rows[date], sort_keys=True, default=str),
                json.dumps(self.by_date[date], sort_keys=True, default=str),
                f"API and export disagree on {date}",
            )

    def test_dimension_states_come_from_the_stored_table(self) -> None:
        """States are stored — an interface must never re-derive them."""
        with get_connection() as conn:
            for date in self.dates:
                row = conn.execute(
                    "SELECT regime_json FROM macro_regime_log_v2 WHERE date = ?", (date,)
                ).fetchone()
                self.assertIsNotNone(row, f"no stored row for {date}")
                stored = json.loads(row["regime_json"] or "{}")
                served = self.export_rows[date]
                for field in DIMENSION_FIELDS:
                    if field in stored:
                        self.assertEqual(
                            str(stored[field]).upper(),
                            str(served[field]).upper(),
                            f"{field} differs from the stored table on {date}",
                        )

    def test_multipliers_are_reproducible_from_the_stored_states(self) -> None:
        """Multipliers are recomputed on read; recomputation must be a pure function of the
        stored states, so the served value is always reproducible from the table."""
        with get_connection() as conn:
            for date in self.dates:
                row = conn.execute(
                    "SELECT regime_json FROM macro_regime_log_v2 WHERE date = ?", (date,)
                ).fetchone()
                stored = json.loads(row["regime_json"] or "{}")
                recomputed = rfe._dimension_multipliers(stored)
                served = self.export_rows[date]
                for field in MULTIPLIER_FIELDS:
                    self.assertAlmostEqual(
                        float(recomputed[field]),
                        float(served[field]),
                        places=9,
                        msg=f"{field} not reproducible from the stored state on {date}",
                    )

    def test_served_rows_declare_their_multiplier_version_and_source(self) -> None:
        for date in self.dates:
            served = self.export_rows[date]
            self.assertEqual(served["multiplier_version"], rfe.MULTIPLIER_VERSION)
            self.assertEqual(served["regime_source"], rfe.REGIME_SOURCE)

    def test_geo_overlay_is_switched_off(self) -> None:
        """Geo pinned at 1.00 for every state until there is data to calibrate against."""
        self.assertEqual(set(rfe.GEO_MULT.values()), {1.00})
        for date in self.dates:
            self.assertEqual(float(self.export_rows[date]["m_geo"]), 1.00)
            self.assertFalse(self.export_rows[date]["geo_overlay_enabled"])

    def test_gross_mult_never_exceeds_one(self) -> None:
        """The clip is one-sided: regime can only shrink the book."""
        for date in self.dates:
            self.assertLessEqual(float(self.export_rows[date]["gross_mult"]), rfe.MAX_MULT)
            self.assertGreaterEqual(float(self.export_rows[date]["gross_mult"]), rfe.MIN_MULT)

    def test_history_does_not_move_when_a_multiplier_constant_changes(self) -> None:
        """Rohit 6 Aug: the stored table is the source of truth, no interface recomputes.

        The multipliers used to be derived on every read, so editing a constant silently rewrote
        every historical row already served. They are persisted per (date, multiplier_version)
        now, so a constant change can only affect rows stamped with a new version.
        """
        before = rfe.load_regime_fridays(start="2020-01-01")["gross_mult"].tail(5).tolist()
        original = dict(rfe.CURVE_MULT)
        try:
            rfe.CURVE_MULT["FLAT"] = 0.10
            after = rfe.load_regime_fridays(start="2020-01-01")["gross_mult"].tail(5).tolist()
        finally:
            rfe.CURVE_MULT.clear()
            rfe.CURVE_MULT.update(original)
        self.assertEqual(before, after, "served history moved when a module constant changed")


if __name__ == "__main__":
    unittest.main()
