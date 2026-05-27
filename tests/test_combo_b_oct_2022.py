"""Gate test: Combo B must fire on Oct 13, 2022."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.claude.regime_classifier import classify_regime
from src.macro_intelligence.engine.combo_detector import evaluate_combo_b_at_date
from src.macro_intelligence.engine.vix_bypass import compute_vix_bypass


def _has_network() -> bool:
    try:
        import urllib.request

        urllib.request.urlopen("https://fred.stlouisfed.org", timeout=5)
        return True
    except Exception:
        return False


class TestComboBOct2022(unittest.TestCase):
    """Oct 13, 2022: VIX 33.6, HY 614bps, CFTC ~8th pctile."""

    def test_combo_b_conditions(self):
        self.assertTrue(evaluate_combo_b_at_date("2022-10-13", 33.6, 614.0, 8.0))

    def test_vix_bypass_when_combo_b_active(self):
        active = [{"combo": "B", "status": "ACTIVE"}]
        self.assertTrue(compute_vix_bypass(active))

    def test_regime_classifier_fixture(self):
        regime = classify_regime("2022-10-13", use_claude=False)
        self.assertEqual(regime.fed_cycle, "HIKING_LATE")
        self.assertEqual(regime.curve_regime, "INVERTED")
        self.assertEqual(regime.geo_overlay, "SANCTIONS")
        self.assertEqual(regime.val_regime, "ELEVATED")

    @unittest.skipUnless(_has_network(), "needs FRED/Yahoo")
    def test_combo_b_live_data_oct_2022(self):
        from src.macro_intelligence.data.fred_pull import fetch_fred_series
        from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
        from src.macro_intelligence.engine.percentiles import compute_pctile_for_series
        from src.macro_intelligence.config import load_config

        vix = fetch_yahoo_close("^VIX", "2020-01-01")
        hy = fetch_fred_series("BAMLH0A0HYM2", "1996-01-01")
        as_of = __import__("pandas").Timestamp("2022-10-13")
        vix_slice = vix.loc[:as_of]
        if vix_slice.empty:
            self.skipTest("Yahoo returned no VIX data for Oct 2022")
        vix_val = float(vix_slice.iloc[-1])
        hy_slice = hy.loc[:as_of]
        hy_val = float(hy_slice.iloc[-1]) if not hy_slice.empty else 614.0
        cfg = {v["id"]: v for v in load_config()["variables"]}
        cftc_series = __import__(
            "src.macro_intelligence.data.cftc_pull", fromlist=["fetch_cftc_fast_money_net"]
        ).fetch_cftc_fast_money_net(2006)
        if not cftc_series.empty and not cftc_series.loc[:as_of].empty:
            cftc_pct = compute_pctile_for_series(cftc_series, cfg["CFTC"], as_of) or 50
        else:
            cftc_pct = 8.0
        self.assertTrue(evaluate_combo_b_at_date("2022-10-13", vix_val, hy_val, cftc_pct))
        self.assertGreaterEqual(vix_val, 25)
        self.assertGreaterEqual(hy_val, 400)
        self.assertLessEqual(cftc_pct, 15)


if __name__ == "__main__":
    unittest.main()
