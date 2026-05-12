"""Tests for chatbot.tools.trading_calculator."""

import importlib.util
import unittest
from pathlib import Path
import sys

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "trading_calculator_under_test",
    _ROOT / "chatbot" / "tools" / "trading_calculator.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_mod)
build_calculator_tool_block = _mod.build_calculator_tool_block
compute_position_mtm_breakdown = _mod.compute_position_mtm_breakdown
compute_row_metrics = _mod.compute_row_metrics
MTM_HOLDING_COLUMN = _mod.MTM_HOLDING_COLUMN

TODAY_PRICE_COLUMN = "Today Trading Date/Price[$], Today Price vs Signal"


class TestComputePositionMtm(unittest.TestCase):
    def test_short_adverse_move_negative_mtm(self):
        out = compute_position_mtm_breakdown(401.24, 520.30, "SHORT")
        self.assertIn("-", out["mtm_percent_display"])
        self.assertLess(float(out["mtm_percent_display"].rstrip("%")), 0)

    def test_long_favorable_positive(self):
        out = compute_position_mtm_breakdown(100.0, 110.0, "Long")
        self.assertGreater(float(out["mtm_percent_display"].rstrip("%")), 0)


class TestBuildCalculatorBlock(unittest.TestCase):
    def test_emits_block_when_today_column_present(self):
        compound = "SOXX, Short, 2026-04-14 (Price: 401.24)"
        today = "2026-05-08 (Price: 520.3000), 29.67% above"
        row = {
            "Function": "DELTADRIFT",
            "Symbol, Signal, Signal Date/Price[$]": compound,
            "Signal Open Price": "401.24",
            TODAY_PRICE_COLUMN: today,
        }
        df = pd.DataFrame([row])
        block = build_calculator_tool_block({"entry": df})
        self.assertIn("CALCULATOR TOOL OUTPUT", block)
        self.assertIn("SOXX", block)
        self.assertIn("MTM=", block)


class TestReportColumnPreferred(unittest.TestCase):
    def test_mtm_holding_column_overrides_recomputed_mtm(self):
        """Pipeline export cell wins vs naive recompute from Today + entry."""
        row = pd.Series(
            {
                "Function": "DELTADRIFT",
                "Symbol, Signal, Signal Date/Price[$]": "SOXX, Long, 2026-04-14 (Price: 401.24)",
                "Signal Open Price": "401.24",
                TODAY_PRICE_COLUMN: "2026-05-08 (Price: 520.30), 29.67% above",
                MTM_HOLDING_COLUMN: "1.00%, 99 days",
            }
        )
        m = compute_row_metrics(row)
        self.assertIsNotNone(m)
        assert m is not None
        self.assertTrue(m.get("mtm_from_report"))
        self.assertEqual(m["mtm_pct"], "1.00%")
        self.assertEqual(m["holding_days"], 99)


class TestParseTodayReuse(unittest.TestCase):
    def test_row_metrics_matches_short_mtm_sign(self):
        row = pd.Series(
            {
                "Function": "X",
                "Symbol, Signal, Signal Date/Price[$]": "SOXX, Short, 2026-04-14 (Price: 401.24)",
                "Signal Open Price": "401.24",
                TODAY_PRICE_COLUMN: "2026-05-08 (Price: 520.30), x",
            }
        )
        m = compute_row_metrics(row)
        self.assertIsNotNone(m)
        assert m is not None
        self.assertEqual(m["side"], "Short")
        self.assertLess(float(m["mtm_pct"].rstrip("%")), 0)


if __name__ == "__main__":
    unittest.main()
