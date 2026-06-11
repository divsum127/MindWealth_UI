"""SSI threshold sweep smoke test."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.analysis.threshold_sweep import sweep_thresholds


class TestSSIThresholdSweep(unittest.TestCase):
    @patch("src.sentiment_superindex.analysis.threshold_sweep.load_spx")
    @patch("src.sentiment_superindex.analysis.threshold_sweep.build_ssi_history_frame")
    def test_sweep_structure(self, mock_hist, mock_spx):
        idx = pd.date_range("2018-01-01", periods=200, freq="B")
        mock_hist.return_value = pd.DataFrame(
            {
                "ssi_level": [0.5 - (i % 20) * 0.05 for i in range(len(idx))],
                "ssi_pctile_5y": [80 - (i % 20) * 2 for i in range(len(idx))],
            },
            index=idx,
        )
        spx_idx = pd.date_range("2018-01-01", periods=300, freq="B")
        mock_spx.return_value = pd.Series(range(3000, 3300), index=spx_idx, dtype=float)

        result = sweep_thresholds(start="2018-06-01", end="2019-12-31")
        self.assertIn("long_pctile_sweep", result)
        self.assertIn("short_pctile_sweep", result)
        self.assertGreater(len(result["long_pctile_sweep"]), 0)
        self.assertIn("recommended", result)


if __name__ == "__main__":
    unittest.main()
