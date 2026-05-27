"""Hit rate SQL helper tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.engine.hit_rates import raw_hit_rate


class TestHitRates(unittest.TestCase):
    def test_raw_hit_rate_empty_db(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            os.environ["MACRO_INTEL_DB"] = str(db)
            init_db(db)
            with get_connection(db) as conn:
                conn.execute(
                    "INSERT INTO combo_fires (date, runic_combo) VALUES ('2020-01-01', 'B')"
                )
                cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO forward_returns (combo_id, spx_3m) VALUES (?, ?)",
                    (cid, 5.0),
                )
            stats = raw_hit_rate("B")
            self.assertEqual(stats["n_obs"], 1)
            self.assertEqual(stats["hit_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
