"""Hit rate tests after seeding combo_fires + forward_returns."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import hit_rate_for_combo
from src.macro_intelligence.db.connection import get_connection, init_db


class TestBackfillHitRates(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.db = Path(self.td.name) / "runic.db"
        os.environ["MACRO_INTEL_DB"] = str(self.db)
        init_db(self.db)
        with get_connection(self.db) as conn:
            for i, ret in enumerate([5.0, 8.0, -2.0, 10.0, 6.0]):
                conn.execute(
                    "INSERT INTO combo_fires (date, runic_combo) VALUES (?, 'B')",
                    (f"2020-0{i+1}-15",),
                )
                cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO forward_returns (combo_id, spx_3m) VALUES (?, ?)",
                    (cid, ret),
                )

    def tearDown(self):
        os.environ.pop("MACRO_INTEL_DB", None)
        self.td.cleanup()

    def test_combo_b_hit_rate_computed(self):
        hr = hit_rate_for_combo("B", bullish=True)
        self.assertEqual(hr["n_obs"], 5)
        self.assertEqual(hr["hit_rate"], 0.8)
        self.assertAlmostEqual(hr["avg_return"], 5.4)


if __name__ == "__main__":
    unittest.main()
