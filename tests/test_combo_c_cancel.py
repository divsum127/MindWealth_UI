"""Combo C cancel counter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.engine.combo_c_cancel import run_combo_c_cancel_check
from src.macro_intelligence.data.bls_pull import ingest_cpi_release


class TestComboCCancel(unittest.TestCase):
    def setUp(self) -> None:
        init_db()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE combo_c_cancel
                SET wti_potential_week=0, active=1, cancel_date=NULL,
                    last_check_date=NULL, cpi_leg_passed=NULL
                WHERE id=1
                """
            )
            conn.commit()
        ingest_cpi_release("2026-05-20", 0.1, 0.3)

    def test_wti_ok_increments_week_on_friday(self) -> None:
        r = run_combo_c_cancel_check("2026-05-22", wti_4wk_pct=2.0, combo_c_active=True)
        self.assertEqual(r["wti_potential_week"], 1)
        self.assertFalse(r["cancelled"])

    def test_fail_resets_counter(self) -> None:
        run_combo_c_cancel_check("2026-05-22", wti_4wk_pct=2.0, combo_c_active=True)
        r = run_combo_c_cancel_check("2026-05-29", wti_4wk_pct=8.0, combo_c_active=True)
        self.assertEqual(r["wti_potential_week"], 0)


if __name__ == "__main__":
    unittest.main()
