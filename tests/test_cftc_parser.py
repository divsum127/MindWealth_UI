"""CFTC TFF parser fixture test."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data.cftc_pull import parse_cftc_dataframe, parse_cftc_rm_dataframe

FIXTURE = Path(__file__).parent / "fixtures" / "cftc" / "tff_sample.csv"


class TestCFTCParser(unittest.TestCase):
    def test_parse_lev_money_net_spx(self):
        df = pd.read_csv(FIXTURE)
        net = parse_cftc_dataframe(df)
        self.assertFalse(net.empty)
        self.assertEqual(len(net), 2)
        oct11 = net.loc[pd.Timestamp("2022-10-11")]
        self.assertEqual(oct11, -60000.0)  # 85000 - 145000 consolidated

    def test_parse_asset_manager_net_spx(self):
        df = pd.read_csv(FIXTURE)
        rm = parse_cftc_rm_dataframe(df)
        self.assertFalse(rm.empty)


if __name__ == "__main__":
    unittest.main()
