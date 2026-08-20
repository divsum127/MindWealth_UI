"""
Regression guard for the "A CPI release is pending this week" sentence.

`_pending_cpi_release` used to scan the trailing 7 days, so the flag stayed
true for a week after a print landed. It was permanently true in practice
because `bls_pull.try_bls_cpi_pull` writes an observation row stamped
`release_date = today` on every nightly run, which always sat inside that
trailing window. The nightly briefing rendered the flag verbatim, so the
report read as a week out of date.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestPendingCpiRelease(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "runic.db"
        self.env = patch.dict(os.environ, {"MACRO_INTEL_DB": str(self.db)}, clear=False)
        self.env.start()

        from src.macro_intelligence.db.connection import get_connection, init_db

        init_db(self.db)
        self._get_connection = get_connection

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def _insert(self, release_date: str, actual: float | None) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pending_releases (release_type, release_date, actual, consensus, source, applied)
                VALUES ('CPI', ?, ?, 0.1, 'test', 0)
                """,
                (release_date, actual),
            )

    def test_released_cpi_does_not_stay_pending(self) -> None:
        from src.macro_intelligence.output.json_writer import _pending_cpi_release

        self._insert("2026-08-12", 0.1)  # printed last Wednesday
        self.assertFalse(
            _pending_cpi_release("2026-08-17"),
            "a CPI that already printed must not read as pending five days later",
        )

    def test_todays_observation_row_does_not_make_it_pending(self) -> None:
        from src.macro_intelligence.output.json_writer import _pending_cpi_release

        # What the nightly BLS pull writes every single run.
        self._insert("2026-08-17", 0.0736)
        self.assertFalse(
            _pending_cpi_release("2026-08-17"),
            "the nightly's own observation row must not be mistaken for a scheduled release",
        )

    def test_upcoming_release_inside_the_window_is_pending(self) -> None:
        from src.macro_intelligence.output.json_writer import _pending_cpi_release

        self._insert("2026-09-11", None)
        self.assertTrue(_pending_cpi_release("2026-09-08"))
        self.assertFalse(
            _pending_cpi_release("2026-09-01"),
            "a release more than 7 days out is not 'this week'",
        )


if __name__ == "__main__":
    unittest.main()
