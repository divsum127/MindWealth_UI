"""WALCL MoM% percentile uses full history on MoM series."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine.percentiles import compute_unconditional_pctile


class TestWalclPercentile(unittest.TestCase):
    def test_near_zero_mom_not_extreme_high(self) -> None:
        cfg = next(v for v in load_config()["variables"] if v["id"] == "WALCL")
        idx = pd.date_range("2008-01-01", periods=400, freq="W-FRI")
        # Mostly small MoM changes; current = 0.03%
        vals = np.random.uniform(-0.5, 0.5, len(idx))
        series = pd.Series(vals, index=idx)
        series.iloc[-1] = 0.03
        pct = compute_unconditional_pctile(series, cfg, pd.Timestamp(idx[-1]))
        self.assertIsNotNone(pct)
        self.assertLess(pct, 75.0)


if __name__ == "__main__":
    unittest.main()
