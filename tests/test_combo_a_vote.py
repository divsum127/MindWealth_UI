"""Combo A direction vote and CONTESTED."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.combo_detector import _combo_a_direction_vote


class TestComboAVote(unittest.TestCase):
    def test_easy_money_vote(self) -> None:
        readings = {
            "NFCI": {"raw_value": -0.5, "direction": None},
            "HY": {"direction": "DOWN"},
            "WALCL": {"direction": "UP"},
            "CNH": {"direction": "DOWN"},
        }
        self.assertEqual(_combo_a_direction_vote(readings, list(readings)), "EASY_MONEY")

    def test_tight_money_vote(self) -> None:
        readings = {
            "NFCI": {"raw_value": 0.5, "direction": None},
            "HY": {"direction": "UP"},
            "WALCL": {"direction": "DOWN"},
            "CNH": {"direction": "UP"},
        }
        self.assertEqual(_combo_a_direction_vote(readings, list(readings)), "TIGHT_MONEY")

    def test_contested_tie(self) -> None:
        readings = {
            "NFCI": {"raw_value": 0.0, "direction": None},
            "HY": {"direction": None},
            "WALCL": {"direction": None},
            "CNH": {"direction": None},
        }
        self.assertEqual(_combo_a_direction_vote(readings, list(readings)), "CONTESTED")


if __name__ == "__main__":
    unittest.main()
