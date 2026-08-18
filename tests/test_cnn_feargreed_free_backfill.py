"""Tests for scripts/backfill_cnn_feargreed_free_sources.py and the provenance-preserving
changes to src/sentiment_superindex/data/cnn_fear_greed.py.

Covers: community CSV parsing, source-tag correctness (real_cnn_api / wayback_reconstructed /
crypto_proxy), the disclosed 2011-01 -> 2012-05-24 window staying untouched (no fabricated data),
and that load_cnn_series() preserves the `source` column on subsequent (nightly-pull-style) runs
instead of silently dropping it.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_script_module():
    path = _ROOT / "scripts" / "backfill_cnn_feargreed_free_sources.py"
    spec = importlib.util.spec_from_file_location("backfill_cnn_feargreed_free_sources", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMUNITY_SAMPLE_CSV = """Date,Open_VIX,High_VIX,Low_VIX,Close_VIX,Adj Close_VIX,Open_SPY,High_SPY,Low_SPY,Close_SPY,Adj Close_SPY,Volume_SPY,Fear Greed
2011-01-03,1,1,1,1,1,1,1,1,1,1,1,68.0
2012-05-24,1,1,1,1,1,1,1,1,1,1,1,20.0
2012-05-25,1,1,1,1,1,1,1,1,1,1,1,13.0
2012-05-29,1,1,1,1,1,1,1,1,1,1,1,14.0
2020-07-08,1,1,1,1,1,1,1,1,1,1,1,
2020-07-13,1,1,1,1,1,1,1,1,1,1,1,53.0
2020-07-14,1,1,1,1,1,1,1,1,1,1,1,55.0
"""


class TestCnnFeargreedFreeBackfill(unittest.TestCase):
    def setUp(self):
        self.mod = _load_script_module()
        self.td = tempfile.TemporaryDirectory()
        self.cache = Path(self.td.name) / "cnn_fear_greed.csv"
        # Point the module under test (and its imports of CNN_CACHE) at a temp cache.
        self.cache.write_text("date,score\n2018-02-01,30.0\n2018-02-03,40.0\n", encoding="utf-8")
        self._patch_cache = mock.patch.object(self.mod, "CNN_CACHE", self.cache)
        self._patch_cache.start()

    def tearDown(self):
        self._patch_cache.stop()
        self.td.cleanup()

    def test_community_csv_parsing(self):
        with mock.patch.object(self.mod, "requests") as mock_requests:
            resp = mock.Mock()
            resp.text = COMMUNITY_SAMPLE_CSV
            resp.raise_for_status = mock.Mock()
            mock_requests.get.return_value = resp
            series = self.mod.fetch_community_series()
        self.assertEqual(len(series), 7)
        self.assertAlmostEqual(series.loc[pd.Timestamp("2012-05-25")], 13.0)
        self.assertTrue(pd.isna(series.loc[pd.Timestamp("2020-07-08")]))

    def test_apply_backfill_tags_sources_correctly(self):
        community = pd.read_csv(io.StringIO(COMMUNITY_SAMPLE_CSV))
        community["Date"] = pd.to_datetime(community["Date"])
        community["Fear Greed"] = pd.to_numeric(community["Fear Greed"], errors="coerce")
        community = community.set_index("Date")["Fear Greed"].sort_index()

        real_cnn = pd.Series({pd.Timestamp("2020-07-14"): 55.0, pd.Timestamp("2020-07-15"): 60.0})
        altme = pd.Series({pd.Timestamp("2020-07-08"): 45.0})

        with mock.patch.object(self.mod, "fetch_community_series", return_value=community), \
             mock.patch.object(self.mod, "fetch_cnn_history", return_value=real_cnn), \
             mock.patch.object(self.mod, "fetch_altme_history", return_value=altme):
            argv_backup = sys.argv
            sys.argv = [
                "backfill_cnn_feargreed_free_sources.py", "--apply",
                "--report", str(Path(self.td.name) / "report.md"),
            ]
            try:
                rc = self.mod.main()
            finally:
                sys.argv = argv_backup
        self.assertEqual(rc, 0)

        out = pd.read_csv(self.cache, parse_dates=["date"]).set_index("date")

        # Window B date (2012-05-25) -> wayback_reconstructed, brand new (cache started 2018-02-01).
        self.assertEqual(out.loc[pd.Timestamp("2012-05-25"), "source"], "wayback_reconstructed")
        self.assertAlmostEqual(out.loc[pd.Timestamp("2012-05-25"), "score"], 13.0)

        # Blank Window-B date (2020-07-08) -> filled from the crypto-proxy fallback.
        self.assertEqual(out.loc[pd.Timestamp("2020-07-08"), "source"], "crypto_proxy")
        self.assertAlmostEqual(out.loc[pd.Timestamp("2020-07-08"), "score"], 45.0)

        # Window A date (2020-07-14) -> real_cnn_api, value from the real CNN series, not the
        # community CSV's value for the same date (real API wins Window A).
        self.assertEqual(out.loc[pd.Timestamp("2020-07-14"), "source"], "real_cnn_api")
        self.assertAlmostEqual(out.loc[pd.Timestamp("2020-07-14"), "score"], 55.0)

        # 2011-01-03: present in the community CSV but BEFORE the verified Window B start
        # (2012-05-25) -> must NOT be ingested (disclosed gap, not fabricated data).
        self.assertNotIn(pd.Timestamp("2011-01-03"), out.index)
        self.assertNotIn(pd.Timestamp("2012-05-24"), out.index)

        # Pre-existing cached date outside every window (2018-02-01 is a Thursday/trading day but
        # not covered by our mocked community/real series) keeps its old value and gets a
        # best-effort 'crypto_proxy' provenance tag rather than being silently dropped.
        self.assertIn(pd.Timestamp("2018-02-01"), out.index)
        self.assertEqual(out.loc[pd.Timestamp("2018-02-01"), "source"], "crypto_proxy")

    def test_load_cnn_series_preserves_source_column_on_rerun(self):
        from src.sentiment_superindex.data import cnn_fear_greed as cnn_mod

        cache = Path(self.td.name) / "cnn_fear_greed_rerun.csv"
        cache.write_text(
            "date,score,source\n"
            "2012-05-25,13.0,wayback_reconstructed\n"
            "2020-07-14,50.0,real_cnn_api\n",
            encoding="utf-8",
        )
        with mock.patch.object(cnn_mod, "CNN_CACHE", cache), \
             mock.patch.object(cnn_mod, "fetch_cnn_history", return_value=pd.Series({pd.Timestamp("2020-07-15"): 60.0})):
            cnn_mod.load_cnn_series()

        out = pd.read_csv(cache, parse_dates=["date"]).set_index("date")
        self.assertIn("source", out.columns)
        self.assertEqual(out.loc[pd.Timestamp("2012-05-25"), "source"], "wayback_reconstructed")
        self.assertEqual(out.loc[pd.Timestamp("2020-07-14"), "source"], "real_cnn_api")
        self.assertEqual(out.loc[pd.Timestamp("2020-07-15"), "source"], "real_cnn_api")


if __name__ == "__main__":
    unittest.main()
