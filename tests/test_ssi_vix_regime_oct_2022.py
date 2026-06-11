"""Oct 2022: VIX sizing vs Combo B vix_bypass (SSI + Runic interaction)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.combo_detector import evaluate_combo_b_at_date
from src.macro_intelligence.engine.vix_bypass import compute_vix_bypass


class TestSSIVixRegimeOct2022(unittest.TestCase):
    """Combo B active on 2022-10-13 => vix_bypass true => C++ ignores SSI size_mult reduction."""

    def test_combo_b_fires_oct_2022(self):
        self.assertTrue(evaluate_combo_b_at_date("2022-10-13", 33.6, 580.0, 8.0))

    def test_vix_bypass_when_combo_b(self):
        active = [{"combo": "B", "status": "ACTIVE"}]
        self.assertTrue(compute_vix_bypass(active, ssi_confirmed_f=False))

    def test_vix_bypass_combo_f_requires_ssi_confirmed(self):
        active = [{"combo": "F", "status": "ACTIVE"}]
        self.assertFalse(compute_vix_bypass(active, ssi_confirmed_f=False))
        self.assertTrue(compute_vix_bypass(active, ssi_confirmed_f=True))


if __name__ == "__main__":
    unittest.main()
