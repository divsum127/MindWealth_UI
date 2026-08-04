"""Tests for CBOE put/call ratio pull + 10-week EMA."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.data.put_call_pull import (
    _parse_cboe_ratio_csv,
    compute_put_call_ema,
    fetch_put_call_ema,
)


CBOE_SAMPLE = """Disclaimer line
DATE,CALLS,PUTS,TOTAL,P/C Ratio
11/1/2006,1401036,1271445,2672481,0.91
11/2/2006,1348240,1218592,2566832,0.90
"""


class TestPutCallPull(unittest.TestCase):
    def test_parse_cboe_ratio_csv(self):
        series = _parse_cboe_ratio_csv(
            CBOE_SAMPLE,
            date_headers=("DATE",),
            ratio_headers=("P/C Ratio",),
        )
        self.assertEqual(len(series), 2)
        self.assertAlmostEqual(float(series.iloc[0]), 0.91)
        self.assertAlmostEqual(float(series.iloc[1]), 0.90)

    def test_compute_put_call_ema(self):
        idx = pd.bdate_range("2020-01-01", periods=80)
        raw = pd.Series(0.80 + (pd.Series(range(80), index=idx) * 0.001), index=idx, name="put_call_ratio")
        ema = compute_put_call_ema(raw, span=10)
        self.assertGreater(len(ema), 0)
        self.assertAlmostEqual(float(ema.iloc[-1]), float(raw.iloc[-1]), places=1)

    @patch("src.sentiment_superindex.data.put_call_pull.fetch_put_call_ratio_raw")
    def test_fetch_put_call_ema_uses_cache_on_empty(self, mock_raw):
        idx = pd.bdate_range("2020-01-01", periods=60)
        mock_raw.return_value = pd.Series(0.85, index=idx, name="put_call_ratio")
        with patch("src.sentiment_superindex.data.put_call_pull.save_cached_series"):
            series = fetch_put_call_ema()
        self.assertGreater(len(series), 0)
        self.assertEqual(series.name, "put_call_ema")


if __name__ == "__main__":
    unittest.main()
