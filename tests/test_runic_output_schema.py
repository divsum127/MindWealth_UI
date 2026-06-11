"""Runic output JSON required fields."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.jobs.nightly_run import run_nightly

REQUIRED = {
    "date",
    "regime",
    "dominant_signal",
    "dominant_reason",
    "brave_fearful",
    "active_combos",
    "ppi_cooling",
    "combo_c_cancel",
    "cftc_status",
}


class TestRunicOutputSchema(unittest.TestCase):
    def test_nightly_payload_fields(self) -> None:
        init_db()
        payload = run_nightly(as_of="2024-09-18", use_claude=False)
        missing = REQUIRED - set(payload.keys())
        self.assertEqual(missing, set(), f"missing keys: {missing}")
        self.assertIn("fed_cycle", payload["regime"])


if __name__ == "__main__":
    unittest.main()
