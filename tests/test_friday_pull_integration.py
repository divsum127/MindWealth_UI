"""Friday pull: all 12 Runic variables persist to daily_readings."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

VAR_IDS = ["NFCI", "HY", "WALCL", "CNH", "WTI", "VIX", "VXTS", "CFTC", "CURVE", "CPI", "GSR", "CAPE"]


def _mock_series():
    idx = pd.date_range("2018-01-01", periods=500, freq="B")
    s = pd.Series(range(500), index=idx, dtype=float)
    curve = pd.DataFrame(
        {"spread_bps": s * 0.01, "steepen_4wk_bps": s * 0.001},
        index=idx,
    )
    return {
        "NFCI": s * 0.001,
        "HY": s * 0.1 + 300,
        "WALCL": s * 0.01,
        "CNH": s * 0.02,
        "WTI": s * 0.05,
        "VIX": s * 0.1 + 15,
        "VXTS": s * 0.001 + 1.0,
        "CFTC": s * 100,
        "CURVE": curve,
        "CPI": s * 0.001,
        "GSR": s * 0.02,
        "CAPE": s * 0.05 + 25,
        "SPX_W": pd.DataFrame({"close": s, "weekly_ret_pct": s * 0.01, "above_50wma": True}, index=idx),
    }


class TestFridayPullIntegration(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.db = Path(self.td.name) / "test_runic.db"
        os.environ["MACRO_INTEL_DB"] = str(self.db)

    def tearDown(self):
        os.environ.pop("MACRO_INTEL_DB", None)
        self.td.cleanup()

    @patch("src.macro_intelligence.data.pull_all.load_all_series")
    def test_pull_all_twelve_variables(self, mock_load):
        from src.macro_intelligence.data.pull_all import pull_all_series, get_readings_as_of
        from src.macro_intelligence.db.connection import init_db

        mock_load.return_value = _mock_series()
        init_db(self.db)
        as_of = "2020-06-26"
        readings = pull_all_series(as_of)
        var_ids = {r["var_id"] for r in readings}
        for vid in VAR_IDS:
            self.assertIn(vid, var_ids, f"missing {vid}")
        stored = get_readings_as_of(as_of)
        self.assertEqual(len(stored), 12)
        for vid in VAR_IDS:
            self.assertIsNotNone(stored[vid].get("raw_value"), vid)


if __name__ == "__main__":
    unittest.main()
