"""Unit tests for portfolio NAV history providers."""

from __future__ import annotations

import unittest

from src.portfolio_nav.service import get_nav_history, nav_history_status, serialize_history
from src.portfolio_nav.stats import beta_sp500, build_daily_nav_points, realized_vol_pct
from src.portfolio_nav.workbook_provider import load_workbook_history, workbook_available


class TestPortfolioNavWorkbook(unittest.TestCase):

    @unittest.skipUnless(workbook_available(), "Ahil workbooks not present")
    def test_workbook_loads_30_months(self) -> None:
        bundle = load_workbook_history("enhanced")
        self.assertEqual(bundle.source, "workbook")
        self.assertEqual(len(bundle.mtm), 30)
        self.assertEqual(len(bundle.closed), 30)
        self.assertEqual(bundle.inception_nav, 10_000_000)
        self.assertGreater(bundle.latest_nav or 0, 10_000_000)

    @unittest.skipUnless(workbook_available(), "Ahil workbooks not present")
    def test_enhanced_attribution_has_four_rows(self) -> None:
        bundle = load_workbook_history("enhanced")
        self.assertEqual(len(bundle.attribution), 4)
        ids = {a.id for a in bundle.attribution}
        self.assertEqual(ids, {"base", "ssi", "cv", "enhanced"})

    @unittest.skipUnless(workbook_available(), "Ahil workbooks not present")
    def test_serialize_includes_risk_metrics(self) -> None:
        bundle = get_nav_history("base")
        payload = serialize_history(bundle)
        self.assertIsNotNone(payload.get("realized_vol_pct"))
        self.assertIsNotNone(payload.get("beta_sp500"))
        self.assertIsNotNone(payload.get("best_month_pct"))
        self.assertIsNotNone(payload.get("worst_month_pct"))

    @unittest.skipUnless(workbook_available(), "Ahil workbooks not present")
    def test_serialize_includes_daily_arrays(self) -> None:
        bundle = get_nav_history("enhanced")
        payload = serialize_history(bundle)
        self.assertIn("mtm_daily", payload)
        self.assertIn("closed_daily", payload)
        self.assertIsInstance(payload["mtm_daily"], list)
        self.assertIsInstance(payload["closed_daily"], list)
        meta = payload.get("nav_series_metadata") or {}
        self.assertIn("mtm_daily_point_count", meta)

    def test_nav_history_status(self) -> None:
        status = nav_history_status()
        self.assertIn("workbook_available", status)
        self.assertIn("engine_available", status)


class TestPortfolioNavStats(unittest.TestCase):

    def test_realized_vol_positive(self) -> None:
        vol = realized_vol_pct([1.0, -0.5, 2.0, 0.3])
        self.assertIsNotNone(vol)
        self.assertGreater(vol, 0)

    def test_beta_computation(self) -> None:
        beta = beta_sp500([1.0, 2.0, -1.0], [0.01, 0.02, -0.01])
        self.assertIsNotNone(beta)

    def test_daily_nav_points_have_drawdown(self) -> None:
        rows = build_daily_nav_points(
            ["2024-01-02", "2024-01-03", "2024-01-04"],
            [10_000_000.0, 10_100_000.0, 9_900_000.0],
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]["drawdown_pct"], round((9_900_000 / 10_100_000 - 1) * 100, 2))


if __name__ == "__main__":
    unittest.main()
