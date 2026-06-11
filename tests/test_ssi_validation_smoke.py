"""Smoke tests for SSI validation analysis (mocked, no network)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.analysis.forward_metrics import summarize_returns


class TestSSIValidationSmoke(unittest.TestCase):
    def test_summarize_returns_structure(self):
        rows = [{"ret_1m": 2.0, "ret_3m": 4.0}, {"ret_1m": -1.0, "ret_3m": 1.0}]
        out = summarize_returns(rows, long_side=True)
        self.assertEqual(out["n_events"], 2)
        self.assertIn("1m", out)
        self.assertGreater(out["1m"]["n"], 0)

    @patch("src.sentiment_superindex.analysis.threshold_sweep.build_ssi_history_frame")
    @patch("src.sentiment_superindex.analysis.threshold_sweep.load_spx")
    def test_threshold_sweep_keys(self, mock_spx, mock_hist):
        idx = pd.date_range("2018-01-01", periods=120, freq="B")
        mock_hist.return_value = pd.DataFrame(
            {"ssi_level": np.linspace(0.5, -0.8, len(idx)), "ssi_pctile_5y": np.linspace(80, 10, len(idx))},
            index=idx,
        )
        mock_spx.return_value = pd.Series(np.linspace(3000, 3500, len(idx)), index=idx)
        from src.sentiment_superindex.analysis.threshold_sweep import sweep_thresholds

        result = sweep_thresholds("2018-06-01", "2019-06-01")
        self.assertIn("long_pctile_sweep", result)
        self.assertIn("short_pctile_sweep", result)

    def test_friday_checklist(self):
        from src.sentiment_superindex.analysis.friday_pull_checklist import run_and_report

        r = run_and_report()
        self.assertEqual(r["test_id"], "16_friday_pull")
        self.assertGreater(len(r["items"]), 5)


if __name__ == "__main__":
    unittest.main()
