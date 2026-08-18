"""Tests for scripts/backfill_hy_oas_from_wayback.py -- real HY OAS history backfill.

Covers: CSV parsing (blank/holiday rows dropped), PROXY -> real tier reclassification on known
dates, provenance tagging in meta_json, disclosed orphan-PROXY handling (wayback has no value for
a date), and that already-real rows keep their raw_value/signal_tier untouched.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402


def _load_script_module():
    path = _ROOT / "scripts" / "backfill_hy_oas_from_wayback.py"
    spec = importlib.util.spec_from_file_location("backfill_hy_oas_from_wayback", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE_CSV = """observation_date,BAMLH0A0HYM2
1996-12-31,3.13
1997-01-01,
1997-01-02,3.06
2008-12-15,21.82
2020-03-23,10.87
2022-06-13,4.87
2023-06-09,4.29
"""


class TestHyOasWaybackBackfill(unittest.TestCase):
    def setUp(self):
        self.mod = _load_script_module()
        self.td = tempfile.TemporaryDirectory()
        self.db = Path(self.td.name) / "runic.db"
        os.environ["MACRO_INTEL_DB"] = str(self.db)
        init_db(self.db)

        # Seed daily_readings with: two PROXY dates covered by the wayback CSV, one PROXY date
        # NOT covered by wayback (orphan), and one already-real date matching the CSV overlap.
        with get_connection(self.db) as conn:
            conn.execute(
                "INSERT INTO daily_readings (date, var_id, raw_value, signal_tier, meta_json) "
                "VALUES ('2008-12-15', 'HY', 12.0, 'PROXY', '{\"proxy\": \"old_model\"}')"
            )
            conn.execute(
                "INSERT INTO daily_readings (date, var_id, raw_value, signal_tier, meta_json) "
                "VALUES ('2020-03-23', 'HY', 5.0, 'PROXY', '{\"proxy\": \"old_model\"}')"
            )
            conn.execute(
                "INSERT INTO daily_readings (date, var_id, raw_value, signal_tier, meta_json) "
                "VALUES ('2009-01-05', 'HY', 15.0, 'PROXY', '{\"proxy\": \"old_model\"}')"
            )
            conn.execute(
                "INSERT INTO daily_readings (date, var_id, raw_value, signal_tier, meta_json) "
                "VALUES ('2023-06-09', 'HY', 4.29, 'NORMAL', '{}')"
            )

    def tearDown(self):
        os.environ.pop("MACRO_INTEL_DB", None)
        self.td.cleanup()

    def test_csv_parsing_drops_blank_rows(self):
        with mock.patch.object(self.mod, "requests") as mock_requests:
            mock_resp = mock.Mock()
            mock_resp.text = SAMPLE_CSV
            mock_resp.raise_for_status = mock.Mock()
            mock_requests.get.return_value = mock_resp
            series = self.mod.fetch_wayback_series()
        self.assertEqual(len(series), 6)  # 7 data rows minus 1 blank (1997-01-01)
        self.assertNotIn(pd.Timestamp("1997-01-01"), series.index)
        self.assertAlmostEqual(series.loc[pd.Timestamp("2008-12-15")], 21.82)

    def test_apply_backfill_reclassifies_and_tags_provenance(self):
        wb_series = pd.read_csv(io.StringIO(SAMPLE_CSV))
        wb_series.columns = ["observation_date", "BAMLH0A0HYM2"]
        wb_series["observation_date"] = pd.to_datetime(wb_series["observation_date"])
        wb_series["BAMLH0A0HYM2"] = pd.to_numeric(wb_series["BAMLH0A0HYM2"], errors="coerce")
        wb_series = wb_series.set_index("observation_date")["BAMLH0A0HYM2"].dropna().sort_index()

        with mock.patch.object(self.mod, "fetch_wayback_series", return_value=wb_series):
            argv_backup = sys.argv
            sys.argv = ["backfill_hy_oas_from_wayback.py", "--apply", "--report", str(Path(self.td.name) / "report.md")]
            try:
                rc = self.mod.main()
            finally:
                sys.argv = argv_backup
        self.assertEqual(rc, 0)

        with get_connection(self.db) as conn:
            rows = {
                r["date"]: dict(r)
                for r in conn.execute("SELECT * FROM daily_readings WHERE var_id='HY'").fetchall()
            }

        # 2008-12-15: PROXY covered by wayback -> real EXTREME, raw_value replaced, provenance tagged.
        row = rows["2008-12-15"]
        self.assertEqual(row["signal_tier"], "EXTREME")
        self.assertAlmostEqual(row["raw_value"], 21.82)
        meta = json.loads(row["meta_json"])
        self.assertEqual(meta["source"], "wayback_fred_archive")
        self.assertIn("archive_url", meta)
        self.assertEqual(meta["snapshot_date"], self.mod.SNAPSHOT_DATE)

        # 2020-03-23: PROXY covered by wayback -> real EXTREME (COVID peak).
        row = rows["2020-03-23"]
        self.assertEqual(row["signal_tier"], "EXTREME")
        self.assertAlmostEqual(row["raw_value"], 10.87)

        # 2009-01-05: PROXY NOT covered by wayback -> orphan, unchanged raw_value/tier.
        row = rows["2009-01-05"]
        self.assertEqual(row["signal_tier"], "PROXY")
        self.assertAlmostEqual(row["raw_value"], 15.0)
        self.assertEqual(json.loads(row["meta_json"]), {"proxy": "old_model"})

        # 2023-06-09: already real -> raw_value/tier untouched.
        row = rows["2023-06-09"]
        self.assertEqual(row["signal_tier"], "NORMAL")
        self.assertAlmostEqual(row["raw_value"], 4.29)

        # 1996-12-31 / 1997-01-02: no prior row existed, wayback has a value -> newly inserted.
        self.assertIn("1996-12-31", rows)
        self.assertAlmostEqual(rows["1996-12-31"]["raw_value"], 3.13)
        self.assertIn("1997-01-02", rows)


if __name__ == "__main__":
    unittest.main()
