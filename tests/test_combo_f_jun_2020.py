"""Gate test: Combo F must fire on Jun 29, 2020."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.claude.regime_classifier import classify_regime
from src.macro_intelligence.engine.combo_detector import evaluate_combo_f_at_date
from src.macro_intelligence.data.yahoo_pull import spx_with_50wma


def _has_network() -> bool:
    try:
        import urllib.request

        urllib.request.urlopen("https://finance.yahoo.com", timeout=5)
        return True
    except Exception:
        return False


class TestComboFJun2020(unittest.TestCase):
    """Jun 29, 2020 (May 26) and Jun 8, 2020 (v3) gate dates."""

    def test_combo_f_v3_jun_8_2020(self):
        self.assertTrue(
            evaluate_combo_f_at_date(
                "2020-06-08",
                weekly_gain_pct=6.2,
                cftc_pctile=31.0,
                above_50wma=True,
                was_below_prior_week=True,
            )
        )

    def test_combo_f_conditions_documented(self):
        self.assertTrue(
            evaluate_combo_f_at_date(
                "2020-06-29",
                weekly_gain_pct=5.1,
                cftc_pctile=31.0,
                above_50wma=True,
                was_below_prior_week=True,
            )
        )

    def test_regime_classifier_fixture(self):
        regime = classify_regime("2020-06-08", use_claude=False)
        self.assertEqual(regime.fed_cycle, "QE")
        self.assertEqual(regime.geo_overlay, "PANDEMIC")

    @unittest.skipUnless(_has_network(), "needs Yahoo")
    def test_combo_f_spx_weekly_jun_2020(self):
        spx_w = spx_with_50wma("2018-01-01")
        as_of = pd.Timestamp("2020-06-26")
        row = spx_w.loc[:as_of].iloc[-1]
        prev = spx_w.loc[:as_of].iloc[-2]
        weekly_gain = float(row["weekly_ret_pct"])
        above = bool(row["above_50wma"])
        was_below = not bool(prev["above_50wma"])
        self.assertGreaterEqual(weekly_gain, 3.0)
        self.assertTrue(
            evaluate_combo_f_at_date(
                "2020-06-29",
                weekly_gain_pct=weekly_gain,
                cftc_pctile=31.0,
                above_50wma=above,
                was_below_prior_week=was_below,
            )
        )


if __name__ == "__main__":
    unittest.main()
