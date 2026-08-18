"""Runic output JSON required fields."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config_paths import MACRO_INTEL_DATA_DIR
from src.macro_intelligence.config import json_output_path
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
    "pre_catalyst",
    "post_event_regime",
}


class TestRunicOutputSchema(unittest.TestCase):
    """`run_nightly` is a job function: it writes both the output snapshot and the DB.

    `persist=False` covers the snapshot; the DB needs `MACRO_INTEL_DB` pointed at a
    throwaway copy, otherwise every run of this test leaves 2024-09-18 rows in
    `daily_readings`, `macro_regime_log`, `cftc_positioning` and `emission_vectors`.
    The live DB is copied rather than started empty so the run does not have to
    re-download every series.
    """

    def setUp(self) -> None:
        self._prev_db = os.environ.get("MACRO_INTEL_DB")
        self._tmp = tempfile.TemporaryDirectory()
        scratch_db = Path(self._tmp.name) / "runic_test.db"
        live_db = Path(self._prev_db) if self._prev_db else MACRO_INTEL_DATA_DIR / "runic.db"
        if live_db.exists():
            shutil.copy2(live_db, scratch_db)
        os.environ["MACRO_INTEL_DB"] = str(scratch_db)

    def tearDown(self) -> None:
        if self._prev_db is None:
            os.environ.pop("MACRO_INTEL_DB", None)
        else:
            os.environ["MACRO_INTEL_DB"] = self._prev_db
        self._tmp.cleanup()

    def test_nightly_payload_fields(self) -> None:
        init_db()
        # persist=False: this test only asserts on returned keys. Without it
        # run_nightly overwrites the live macro_intelligence/output snapshot
        # the API serves with 2024-09-18 data.
        payload = run_nightly(as_of="2024-09-18", use_claude=False, persist=False)
        missing = REQUIRED - set(payload.keys())
        self.assertEqual(missing, set(), f"missing keys: {missing}")
        self.assertIn("fed_cycle", payload["regime"])

    def test_nightly_does_not_touch_live_snapshot(self) -> None:
        live = json_output_path()
        before = live.stat().st_mtime_ns if live.exists() else None
        run_nightly(as_of="2024-09-18", use_claude=False, persist=False)
        after = live.stat().st_mtime_ns if live.exists() else None
        self.assertEqual(before, after, f"run_nightly(persist=False) wrote {live}")


if __name__ == "__main__":
    unittest.main()
