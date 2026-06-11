"""Validate CFTC TFF column manifest vs fixture and parser."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data.cftc_pull import parse_cftc_dataframe, parse_cftc_rm_dataframe

MANIFEST = _ROOT / "macro_intelligence" / "CFTC_TFF_COLUMNS.yaml"
FIXTURE = Path(__file__).parent / "fixtures" / "cftc" / "tff_sample.csv"


class TestCftcColumnManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        cls.required = cls.manifest["required_columns"]

    def test_manifest_required_columns_in_fixture(self) -> None:
        df = pd.read_csv(FIXTURE)
        for col in self.required.values():
            self.assertIn(col, df.columns, msg=f"missing {col}")

    def test_consolidated_fm_net_oct_2022(self) -> None:
        df = pd.read_csv(FIXTURE)
        fm = parse_cftc_dataframe(df)
        self.assertEqual(len(fm), 2)
        oct11 = fm.loc[pd.Timestamp("2022-10-11")]
        self.assertEqual(oct11, 85000 - 145000)

    def test_consolidated_rm_net_oct_2022(self) -> None:
        df = pd.read_csv(FIXTURE)
        rm = parse_cftc_rm_dataframe(df)
        oct11 = rm.loc[pd.Timestamp("2022-10-11")]
        self.assertEqual(oct11, 210000 - 155000)

    def test_manifest_matches_cftc_official_field_ids(self) -> None:
        # CFTC cotvariablestfm fields 1,3,12-13,15-16
        self.assertEqual(self.required["market"], "Market_and_Exchange_Names")
        self.assertEqual(self.required["fm_long"], "Lev_Money_Positions_Long_All")
        self.assertEqual(self.required["fm_short"], "Lev_Money_Positions_Short_All")
        self.assertEqual(self.required["rm_long"], "Asset_Mgr_Positions_Long_All")
        self.assertEqual(self.required["rm_short"], "Asset_Mgr_Positions_Short_All")


if __name__ == "__main__":
    unittest.main()
