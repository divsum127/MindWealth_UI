"""Percentile engine unit tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.percentiles import percentile_rank, compute_pctile_for_series
from src.macro_intelligence.models import SignalTier
from src.macro_intelligence.engine.percentiles import evaluate_variable_tier


class TestPercentiles(unittest.TestCase):
    def test_percentile_rank_extreme_high(self):
        hist = pd.Series(np.linspace(0, 100, 101))
        p = percentile_rank(99.0, hist)
        self.assertIsNotNone(p)
        self.assertGreater(p, 95)

    def test_vix_rare_tier(self):
        cfg = {
            "paradigm": "DUAL",
            "rare": {"abs_level": 25, "high_pctile": 80},
            "extreme": {"abs_level": 35, "high_pctile": 95},
        }
        tier, direction = evaluate_variable_tier("VIX", cfg, 33.6, 85.0)
        self.assertEqual(tier, SignalTier.RARE)
        self.assertEqual(direction, "UP")


if __name__ == "__main__":
    unittest.main()
