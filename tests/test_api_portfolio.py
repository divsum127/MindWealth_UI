"""Tests for portfolio API endpoints.

Covers:
  GET  /api/v1/portfolio/sizer
  GET  /api/v1/portfolio/risk
  POST /api/v1/portfolio/risk/analyze
  GET  /api/v1/portfolio/risk/search
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from api.services import portfolio_service as portfolio_svc
from tests.api_test_helpers import disable_rate_limits

client = TestClient(app)

# ─────────────────────────────────────────────────────────────────────────────
# Shared mock data
# ─────────────────────────────────────────────────────────────────────────────

_MOCK_RUNIC: dict = {
    "date": "2026-06-23",
    "regime": {"valuation": "EXTREME", "geo": "NEUTRAL"},
    "active_combos": [{"combo": "C", "duration_weeks": 11, "hit_rate_3m": 83}],
    "watch_combos": [],
    "variables_dashboard": [
        {"variable": "VIX",  "current": 16.4, "percentile": 40},
        {"variable": "HY",   "current": 318,  "tier": "NORMAL"},
        {"variable": "CAPE", "current": 42,   "tier": "EXTREME"},
    ],
    "system_recommendation": "Reduce new longs; Combo C active.",
}

_MOCK_SSI: dict = {
    "date": "2026-06-23",
    "ssi_multiplier": 1.0,
    "ssi_level": -0.2,
    "layer2_status": "NEUTRAL",
    "layer2_confirmed_count": 1,
}

_MOCK_CORR_LABELS = [
    "global_risk_on", "semiconductors", "financials", "commodities",
    "canada_def", "us_tech", "india", "bonds",
]
_MOCK_CORR_MATRIX = [
    [1.0, 0.75, 0.59, 0.29, 0.70, 0.94, 0.53, 0.19],
    [0.75, 1.0, 0.19, 0.31, 0.48, 0.86, 0.37, 0.11],
    [0.59, 0.19, 1.0, 0.04, 0.51, 0.38, 0.34, 0.10],
    [0.29, 0.31, 0.04, 1.0, 0.59, 0.30, 0.19, 0.13],
    [0.70, 0.48, 0.51, 0.59, 1.0, 0.60, 0.42, 0.21],
    [0.94, 0.86, 0.38, 0.30, 0.60, 1.0, 0.47, 0.15],
    [0.53, 0.37, 0.34, 0.19, 0.42, 0.47, 1.0, 0.28],
    [0.19, 0.11, 0.10, 0.13, 0.21, 0.15, 0.28, 1.0],
]


def _mock_names(symbols: set[str], **_: object) -> dict[str, str]:
    return {s: f"{s} Inc." for s in symbols}


def _mock_corr() -> tuple[list[str], list[list[float]], dict]:
    return _MOCK_CORR_LABELS, _MOCK_CORR_MATRIX, {"source": "test"}


class _PortfolioTestMixin:
    """Patch slow external lookups for unit tests."""

    def setUp(self) -> None:
        disable_rate_limits()
        self._patches = [
            patch("api.services.portfolio_service._compute_spx_trend_mult", return_value=(1.0, {})),
            patch("api.services.portfolio_service._refresh_ticker_names_cache", side_effect=_mock_names),
            patch("api.services.portfolio_service._load_correlation_matrix", side_effect=_mock_corr),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Sizer tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolioSizer(_PortfolioTestMixin, unittest.TestCase):

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_returns_200(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        self.assertEqual(r.status_code, 200)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_top_level_keys(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        body = r.json()
        for key in ("date", "as_of", "scenario", "scenarios_available", "ceiling", "summary", "clusters", "pnl_rows", "constraints"):
            self.assertIn(key, body, f"Missing key: {key}")

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_ceiling_fields(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        ceiling = r.json()["ceiling"]
        for key in ("final_ceiling_pct", "portfolio_notional", "formula_text", "regime_max_pct"):
            self.assertIn(key, ceiling, f"ceiling missing: {key}")
        self.assertEqual(ceiling["portfolio_notional"], 100_000_000)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_summary_fields(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        summary = r.json()["summary"]
        for key in ("deployed_usd", "deployed_pct", "cash_usd", "cash_pct", "idle_income_usd", "open_position_count"):
            self.assertIn(key, summary)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_scenarios(self, *_mocks) -> None:
        for scenario in ("normal", "stress", "lowvol"):
            r = client.get(f"/api/v1/portfolio/sizer?scenario={scenario}")
            self.assertEqual(r.status_code, 200, f"Failed for scenario={scenario}")
            self.assertEqual(r.json()["scenario"], scenario)

    def test_sizer_invalid_scenario(self) -> None:
        r = client.get("/api/v1/portfolio/sizer?scenario=moon")
        self.assertEqual(r.status_code, 422)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_cluster_structure(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        clusters = r.json()["clusters"]
        self.assertIsInstance(clusters, list)
        self.assertGreater(len(clusters), 0)
        first = clusters[0]
        for key in ("id", "label", "budget_usd", "budget_pct", "deployed_usd", "deployed_pct", "positions"):
            self.assertIn(key, first)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_scenarios_available_true(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        self.assertTrue(r.json()["scenarios_available"])

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_stress_ceiling_lower_than_normal(self, *_mocks) -> None:
        normal = client.get("/api/v1/portfolio/sizer?scenario=normal").json()["ceiling"]["final_ceiling_pct"]
        stress = client.get("/api/v1/portfolio/sizer?scenario=stress").json()["ceiling"]["final_ceiling_pct"]
        self.assertGreater(normal, stress)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_combo_c_constraint_present(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        constraints = r.json()["constraints"]
        titles = [c["title"] for c in constraints]
        self.assertIn("Combo C active", titles)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_pnl_rows_structure(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        pnl_rows = r.json()["pnl_rows"]
        self.assertIsInstance(pnl_rows, list)
        if pnl_rows:
            row = pnl_rows[0]
            for key in ("ticker", "direction", "size_tier", "allocation_usd", "flags", "blocked"):
                self.assertIn(key, row)


    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_cluster_deployed_within_equity_ceiling(self, *_mocks) -> None:
        from api.services.portfolio_service import get_portfolio_sizer

        body = get_portfolio_sizer("normal")
        notional = body["ceiling"]["portfolio_notional"]
        deployed_cap = round(body["ceiling"]["final_ceiling_pct"] / 100 * notional)
        cluster_deployed = sum(c["deployed_usd"] for c in body["clusters"])
        self.assertEqual(cluster_deployed, deployed_cap)
        self.assertEqual(cluster_deployed, body["summary"]["deployed_usd"])
        for cluster in body["clusters"]:
            self.assertLessEqual(cluster["deployed_usd"], cluster["budget_usd"])
            self.assertLessEqual(cluster["budget_usd"], deployed_cap)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_pnl_rows_have_names(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        pnl_rows = r.json()["pnl_rows"]
        if pnl_rows:
            for row in pnl_rows[:5]:
                self.assertIsNotNone(row.get("name"))
                self.assertNotEqual(row.get("name"), "")
                self.assertEqual(row.get("win_rate_label"), "Backtested Win Rate")

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_pnl_rows_have_cross_function_asset_class_status(self, *_mocks) -> None:
        """HANDOFF §7 / DATA_ISSUES §6 gap — pnl_rows/positions must carry cross_function_exit,
        asset_class, status. Was missing on live API before this fix."""
        r = client.get("/api/v1/portfolio/sizer")
        pnl_rows = r.json()["pnl_rows"]
        self.assertGreater(len(pnl_rows), 0)
        for row in pnl_rows[:20]:
            self.assertIn("cross_function_exit", row)
            self.assertIsInstance(row["cross_function_exit"], bool)
            self.assertIn("asset_class", row)
            self.assertIsInstance(row["asset_class"], str)
            self.assertNotEqual(row["asset_class"], "")
            self.assertIn(row["status"], ("Open", "Blocked"))
            self.assertEqual(row["status"], "Blocked" if row["blocked"] else "Open")
        # Same sized_row dict backs cluster positions[] — fields must be there too (HANDOFF §7).
        for cluster in r.json()["clusters"][:3]:
            for pos in cluster["positions"][:5]:
                self.assertIn("cross_function_exit", pos)
                self.assertIn("asset_class", pos)
                self.assertIn("status", pos)

    def test_asset_class_label_mapping(self) -> None:
        from api.services.portfolio_service import _asset_class_label

        self.assertEqual(_asset_class_label("EQUITY"), "Equity")
        self.assertEqual(_asset_class_label("ETF"), "ETF")
        self.assertEqual(_asset_class_label("CRYPTOCURRENCY"), "Cryptocurrency")
        self.assertEqual(_asset_class_label("CURRENCY"), "Currency")
        self.assertEqual(_asset_class_label(""), "Equity")
        self.assertEqual(_asset_class_label(None), "Equity")

    def test_bq_tier_nan_treated_as_missing(self) -> None:
        from api.services.portfolio_service import _bq_tier
        import math

        label, share = _bq_tier(float("nan"))
        self.assertEqual(label, "REDUCED")
        self.assertGreater(share, 0.0)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_not_applicable_etf_not_blocked(self, *_mocks) -> None:
        from api.services.portfolio_service import get_portfolio_sizer

        body = get_portfolio_sizer("normal")
        na_positions = [
            pos
            for cluster in body["clusters"]
            for pos in cluster["positions"]
            if pos.get("not_applicable")
        ]
        self.assertGreater(len(na_positions), 0, "Expected NOT_APPLICABLE positions in sizer output")
        for pos in na_positions:
            self.assertFalse(pos["blocked"], f"{pos['ticker']} should not be blocked when conviction N/A")
            self.assertGreater(pos["allocation_usd"], 0, f"{pos['ticker']} should receive base allocation")
            self.assertIsNone(pos["bq_score"])
            self.assertTrue(str(pos["size_tier"]).startswith("N/A"))

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_sizer_no_unscored_when_overlay_stale(self, *_mocks) -> None:
        from api.services.portfolio_service import get_portfolio_sizer

        body = get_portfolio_sizer("normal")
        unscored = [
            pos
            for cluster in body["clusters"]
            for pos in cluster["positions"]
            if pos.get("unscored")
        ]
        self.assertEqual(
            unscored,
            [],
            f"Expected on-demand conviction merge; got unscored: "
            f"{[p['ticker'] for p in unscored[:10]]}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Risk tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolioRisk(_PortfolioTestMixin, unittest.TestCase):

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_risk_returns_200(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/risk")
        self.assertEqual(r.status_code, 200)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_risk_top_level_keys(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/risk")
        body = r.json()
        for key in ("labels", "matrix", "breaches", "cluster_weights"):
            self.assertIn(key, body)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_risk_matrix_shape(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/risk")
        body = r.json()
        labels = body["labels"]
        matrix = body["matrix"]
        self.assertEqual(len(matrix), len(labels))
        for row in matrix:
            self.assertEqual(len(row), len(labels))

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_risk_matrix_diagonal_one(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/risk")
        matrix = r.json()["matrix"]
        for i, row in enumerate(matrix):
            self.assertAlmostEqual(row[i], 1.0, places=3)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_risk_breaches_have_required_fields(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/risk")
        for breach in r.json()["breaches"]:
            for key in ("pair", "rho", "level", "combined_weight_pct"):
                self.assertIn(key, breach)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_risk_breaches_above_threshold(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/risk")
        for breach in r.json()["breaches"]:
            self.assertGreater(breach["rho"], 0.75)


    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_risk_scenario_param(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/risk?scenario=stress")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["scenario"], "stress")
        self.assertIn("correlation_meta", r.json())


# ─────────────────────────────────────────────────────────────────────────────
# Holdings analysis tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeHoldings(_PortfolioTestMixin, unittest.TestCase):

    @patch("api.services.portfolio_service._fetch_price_safe", return_value=100.0)
    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_analyze_returns_200(self, *_mocks) -> None:
        r = client.post(
            "/api/v1/portfolio/risk/analyze",
            json={"holdings": [{"symbol": "SPY", "quantity": 100}], "cash_usd": 5000},
        )
        self.assertEqual(r.status_code, 200)

    @patch("api.services.portfolio_service._fetch_price_safe", return_value=100.0)
    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_analyze_top_level_keys(self, *_mocks) -> None:
        r = client.post(
            "/api/v1/portfolio/risk/analyze",
            json={"holdings": [{"symbol": "SPY", "quantity": 50}]},
        )
        body = r.json()
        for key in ("total_notional_usd", "positions", "cluster_weights", "concentration_warnings", "correlation_breaches"):
            self.assertIn(key, body)

    def test_analyze_empty_holdings_returns_400(self) -> None:
        r = client.post(
            "/api/v1/portfolio/risk/analyze",
            json={"holdings": []},
        )
        self.assertEqual(r.status_code, 400)

    def test_analyze_missing_body_returns_422(self) -> None:
        r = client.post("/api/v1/portfolio/risk/analyze", json={})
        self.assertEqual(r.status_code, 422)


# ─────────────────────────────────────────────────────────────────────────────
# Ticker search tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTickerSearch(_PortfolioTestMixin, unittest.TestCase):

    def test_search_returns_200(self) -> None:
        r = client.get("/api/v1/portfolio/risk/search?q=SP")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_search_empty_q_returns_400(self) -> None:
        r = client.get("/api/v1/portfolio/risk/search?q= ")
        self.assertEqual(r.status_code, 400)

    def test_search_missing_q_returns_422(self) -> None:
        r = client.get("/api/v1/portfolio/risk/search")
        self.assertEqual(r.status_code, 422)

    def test_search_results_have_symbol(self) -> None:
        r = client.get("/api/v1/portfolio/risk/search?q=A")
        for item in r.json():
            self.assertIn("symbol", item)
            self.assertIn("name", item)


# ─────────────────────────────────────────────────────────────────────────────
# Holdings + book_id + sizing alias
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolioNav(_PortfolioTestMixin, unittest.TestCase):

    def test_nav_model_enhanced_returns_200(self) -> None:
        r = client.get(
            "/api/v1/portfolio/nav",
            params={"book_id": "model", "book": "enhanced"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["book_id"], "model")
        self.assertEqual(body["book"], "enhanced")
        for key in (
            "nav", "as_of", "deployed_pct", "cash_pct", "position_count",
            "conviction_summary", "mtm", "waterfall_steps", "top_contributors",
        ):
            self.assertIn(key, body)

    def test_nav_unsupported_book_returns_422(self) -> None:
        r = client.get(
            "/api/v1/portfolio/nav",
            params={"book_id": "brokerage", "book": "enhanced"},
        )
        self.assertEqual(r.status_code, 422)

    def test_nav_model_base_returns_200_with_history(self) -> None:
        r = client.get(
            "/api/v1/portfolio/nav",
            params={"book_id": "model", "book": "base"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertGreaterEqual(len(body.get("mtm") or []), 2)
        self.assertGreaterEqual(len(body.get("benchmark") or []), 2)
        self.assertTrue(body.get("nav_series_source"))
        self.assertIsNotNone(body.get("since_go_live_pct"))
        self.assertIsNotNone(body.get("realized_vol_pct"))

    def test_nav_monthly_series_has_drawdown(self) -> None:
        body = client.get(
            "/api/v1/portfolio/nav",
            params={"book_id": "model", "book": "enhanced"},
        ).json()
        point = (body.get("mtm") or [])[-1]
        for key in ("date", "value", "drawdown_pct", "high_water_mark"):
            self.assertIn(key, point)

    def test_nav_includes_daily_series_fields(self) -> None:
        body = client.get(
            "/api/v1/portfolio/nav",
            params={"book_id": "model", "book": "enhanced"},
        ).json()
        self.assertIn("mtm_daily", body)
        self.assertIn("closed_daily", body)
        self.assertIsInstance(body["mtm_daily"], list)
        self.assertIsInstance(body["closed_daily"], list)
        if body.get("nav_series_source") == "nav_engine" and body["mtm_daily"]:
            day = body["mtm_daily"][-1]
            for key in ("date", "value", "drawdown_pct", "high_water_mark"):
                self.assertIn(key, day)

    def test_nav_portfolio_notional_fields(self) -> None:
        body = client.get(
            "/api/v1/portfolio/sizer",
            params={"scenario": "normal"},
        ).json()
        self.assertEqual(body["ceiling"]["portfolio_notional"], 100_000_000)
        self.assertEqual(body["ceiling"]["portfolio_notional_source"], "default")
        nav = client.get(
            "/api/v1/portfolio/nav",
            params={"book_id": "model", "book": "enhanced"},
        ).json()
        self.assertEqual(nav.get("portfolio_notional_usd"), 100_000_000)
        self.assertEqual(nav.get("portfolio_notional_source"), "default")

    def test_holdings_base_still_422(self) -> None:
        r = client.get(
            "/api/v1/portfolio/holdings",
            params={"book_id": "model", "book": "base"},
        )
        self.assertEqual(r.status_code, 422)

    def test_nav_position_count_matches_holdings(self) -> None:
        nav = client.get(
            "/api/v1/portfolio/nav",
            params={"book_id": "model", "book": "enhanced"},
        ).json()
        holdings = client.get(
            "/api/v1/portfolio/holdings",
            params={"book_id": "model", "book": "enhanced"},
        ).json()
        self.assertEqual(nav["position_count"], len(holdings.get("holdings", [])))


class TestPortfolioHoldings(_PortfolioTestMixin, unittest.TestCase):

    def test_holdings_model_enhanced_returns_200(self) -> None:
        r = client.get(
            "/api/v1/portfolio/holdings",
            params={"book_id": "model", "book": "enhanced"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["book_id"], "model")
        self.assertEqual(body["book"], "enhanced")
        self.assertIn("holdings", body)
        self.assertIn("as_of", body)
        if body["holdings"]:
            h = body["holdings"][0]
            for key in (
                "ticker", "score", "rank", "size_usd", "same_asset_siblings",
                "multi_sig", "rr_dynamic", "hold_time_used_pct", "sleeve",
            ):
                self.assertIn(key, h)

    def test_holdings_unsupported_book_returns_422(self) -> None:
        r = client.get(
            "/api/v1/portfolio/holdings",
            params={"book_id": "model", "book": "base"},
        )
        self.assertEqual(r.status_code, 422)

    def test_holdings_brokerage_returns_422(self) -> None:
        r = client.get(
            "/api/v1/portfolio/holdings",
            params={"book_id": "brokerage", "book": "enhanced"},
        )
        self.assertEqual(r.status_code, 422)


class TestPortfolioSizingAlias(_PortfolioTestMixin, unittest.TestCase):

    def test_sizing_alias_matches_sizer(self) -> None:
        r1 = client.get("/api/v1/portfolio/sizer", params={"book_id": "model", "scenario": "normal"})
        r2 = client.get("/api/v1/portfolio/sizing", params={"book_id": "model", "scenario": "normal"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()["summary"], r2.json()["summary"])

    def test_sizer_includes_book_id(self) -> None:
        r = client.get("/api/v1/portfolio/sizer", params={"book_id": "model"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("book_id"), "model")

    def test_risk_includes_conviction_summary(self) -> None:
        r = client.get("/api/v1/portfolio/risk", params={"book_id": "model", "scenario": "normal"})
        self.assertEqual(r.status_code, 200)
        cs = r.json().get("conviction_summary")
        self.assertIsInstance(cs, dict)
        self.assertIn("max_count", cs)


class TestPortfolioNotional(unittest.TestCase):

    def tearDown(self) -> None:
        for key in ("PORTFOLIO_NOTIONAL", "PORTFOLIO_USE_RESEARCH_NOTIONAL"):
            os.environ.pop(key, None)

    def test_default_notional_100m(self) -> None:
        self.assertEqual(portfolio_svc.get_portfolio_notional(), 100_000_000)
        self.assertEqual(portfolio_svc.portfolio_notional_source(), "default")

    def test_env_override(self) -> None:
        os.environ["PORTFOLIO_NOTIONAL"] = "25000000"
        self.assertEqual(portfolio_svc.get_portfolio_notional(), 25_000_000)
        self.assertEqual(portfolio_svc.portfolio_notional_source(), "env")

    def test_research_flag_uses_yaml(self) -> None:
        os.environ["PORTFOLIO_USE_RESEARCH_NOTIONAL"] = "1"
        self.assertEqual(portfolio_svc.get_portfolio_notional(), 10_000_000)
        self.assertEqual(portfolio_svc.portfolio_notional_source(), "research")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — AUTO / MANUAL sizing scenarios, manual overrides CRUD, alerts, regime-history
# ─────────────────────────────────────────────────────────────────────────────

class TestScenarioMetaAndAlerts(_PortfolioTestMixin, unittest.TestCase):

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_auto_scenario_resolves_to_a_base_scenario(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer", params={"scenario": "auto"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["scenario"], "auto")
        self.assertIn(body["auto_resolved_scenario"], ("normal", "stress", "lowvol"))
        self.assertIn("auto_resolution_reason", body)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_manual_scenario_applies_override(self, *_mocks) -> None:
        from api.services import manual_overrides_service

        with tempfile.TemporaryDirectory() as tmp:
            override_path = Path(tmp) / "overrides.json"
            with patch.object(manual_overrides_service, "_STORE_PATH", override_path):
                base = client.get("/api/v1/portfolio/sizer", params={"scenario": "normal"}).json()
                sample = next(
                    row for row in base["pnl_rows"]
                    if not row.get("blocked") and row.get("allocation_usd")
                )
                r = client.post(
                    "/api/v1/portfolio/sizing/manual-overrides",
                    json={
                        "ticker": sample["ticker"], "function": sample["function"],
                        "interval": sample["interval"], "direction": sample.get("direction") or "Long",
                        "allocation_usd": 987654,
                    },
                )
                self.assertEqual(r.status_code, 200, r.text)

                listed = client.get("/api/v1/portfolio/sizing/manual-overrides").json()
                self.assertEqual(len(listed["overrides"]), 1)

                manual = client.get("/api/v1/portfolio/sizer", params={"scenario": "manual"}).json()
                self.assertEqual(manual["scenario"], "manual")
                self.assertGreaterEqual(manual["manual_overrides_applied"], 1)
                matched = next(
                    row for row in manual["pnl_rows"]
                    if row.get("ticker") == sample["ticker"] and row.get("manual_override")
                )
                self.assertEqual(matched["allocation_usd"], 987654)

                r = client.delete(
                    "/api/v1/portfolio/sizing/manual-overrides",
                    params={
                        "ticker": sample["ticker"], "function": sample["function"],
                        "interval": sample["interval"], "direction": sample.get("direction") or "Long",
                    },
                )
                self.assertEqual(r.status_code, 200)

    def test_manual_override_negative_allocation_returns_400(self) -> None:
        r = client.post(
            "/api/v1/portfolio/sizing/manual-overrides",
            json={"ticker": "AAPL", "allocation_usd": -100},
        )
        self.assertEqual(r.status_code, 400)

    def test_remove_nonexistent_override_returns_404(self) -> None:
        r = client.delete(
            "/api/v1/portfolio/sizing/manual-overrides",
            params={"ticker": "ZZZZZ_NOPE"},
        )
        self.assertEqual(r.status_code, 404)

    @patch("api.services.portfolio_service._load_runic_safe", return_value=_MOCK_RUNIC)
    @patch("api.services.portfolio_service._load_ssi_safe", return_value=_MOCK_SSI)
    def test_alerts_returns_200_with_expected_shape(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/alerts")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        for key in ("book_id", "as_of", "alert_count", "alerts"):
            self.assertIn(key, body)
        self.assertEqual(body["alert_count"], len(body["alerts"]))
        for alert in body["alerts"][:5]:
            for key in ("id", "type", "severity", "title", "body", "target_page"):
                self.assertIn(key, alert)

    def test_regime_history_returns_200_with_data_status(self) -> None:
        r = client.get("/api/v1/portfolio/regime-history")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("series", body)
        self.assertIn("data_status", body)
        self.assertIn("note", body["data_status"])

    def test_regime_history_invalid_scenario_returns_422(self) -> None:
        r = client.get("/api/v1/portfolio/regime-history", params={"scenario": "moon"})
        self.assertEqual(r.status_code, 422)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 — personal book CRUD + NAV/Holdings, brokerage still blocked
# ─────────────────────────────────────────────────────────────────────────────

class TestPersonalBookApi(_PortfolioTestMixin, unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        from api.services import personal_book_service
        from src.portfolio_nav import book_snapshot_store

        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = Path(self._tmpdir.name) / "personal_holdings.json"
        self._db_path = Path(self._tmpdir.name) / "test_snapshots.db"
        self._patches2 = [
            patch.object(personal_book_service, "PERSONAL_HOLDINGS_JSON", self._path),
            patch.object(personal_book_service, "_live_price", return_value=250.0),
            patch.object(personal_book_service, "_ticker_name", return_value="Apple Inc."),
            patch.object(book_snapshot_store, "BOOK_SNAPSHOTS_DB", self._db_path),
        ]
        for p in self._patches2:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches2):
            p.stop()
        self._tmpdir.cleanup()
        super().tearDown()

    def test_add_list_remove_holding(self) -> None:
        r = client.post(
            "/api/v1/portfolio/personal/holdings",
            json={"ticker": "aapl", "shares": 10, "cost_basis": 150.0, "entry_date": "2025-01-15"},
        )
        self.assertEqual(r.status_code, 200, r.text)

        r = client.get("/api/v1/portfolio/personal/holdings")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["holdings"]), 1)

        r = client.delete("/api/v1/portfolio/personal/holdings", params={"ticker": "AAPL"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["removed"])

    def test_remove_nonexistent_holding_returns_404(self) -> None:
        r = client.delete("/api/v1/portfolio/personal/holdings", params={"ticker": "NOPE"})
        self.assertEqual(r.status_code, 404)

    def test_set_cash(self) -> None:
        r = client.put("/api/v1/portfolio/personal/cash", json={"cash_usd": 2500.0})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["cash_usd"], 2500.0)

    def test_personal_nav_snapshot(self) -> None:
        client.post(
            "/api/v1/portfolio/personal/holdings",
            json={"ticker": "AAPL", "shares": 10, "cost_basis": 150.0},
        )
        r = client.get("/api/v1/portfolio/nav", params={"book_id": "personal"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["book_id"], "personal")
        self.assertIsNone(body["book"])
        self.assertEqual(body["nav"], 2500.0)  # 10 * 250.0
        self.assertEqual(body["mtm"], [])
        self.assertEqual(body["data_status"]["status"], "live_snapshot_only")

    def test_personal_holdings_view(self) -> None:
        client.post(
            "/api/v1/portfolio/personal/holdings",
            json={"ticker": "AAPL", "shares": 10, "cost_basis": 150.0},
        )
        r = client.get("/api/v1/portfolio/holdings", params={"book_id": "personal"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["book_id"], "personal")
        self.assertEqual(len(body["holdings"]), 1)
        self.assertEqual(body["holdings"][0]["ticker"], "AAPL")

    def test_personal_sizer_still_blocked(self) -> None:
        r = client.get("/api/v1/portfolio/sizer", params={"book_id": "personal"})
        self.assertEqual(r.status_code, 422)

    def test_personal_risk_still_blocked(self) -> None:
        r = client.get("/api/v1/portfolio/risk", params={"book_id": "personal"})
        self.assertEqual(r.status_code, 422)

    def test_brokerage_nav_still_blocked(self) -> None:
        r = client.get("/api/v1/portfolio/nav", params={"book_id": "brokerage", "book": "enhanced"})
        self.assertEqual(r.status_code, 422)

    def test_brokerage_holdings_still_blocked(self) -> None:
        r = client.get("/api/v1/portfolio/holdings", params={"book_id": "brokerage", "book": "enhanced"})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()


class TestAxiom2CeilingBounds(unittest.TestCase):
    """Can portfolio_service produce an allocation the axioms forbid?

    Rohit 6 Aug: his own spec example, 85% low-vol cap x 1.20 VIX x 1.20 SSI, multiplies out
    to a 104% equity ceiling — a levered book — which violates Axiom 2. "So either
    portfolio_service can produce an allocation the axioms forbid, or the axioms bind and
    those x1.20 terms have never done anything. Establish which before we build on top."

    Answer: the axioms bind. The SSI term is capped at 1.00 and the final ceiling is
    min(100, ...), so no combination of inputs reaches 104%. These tests pin that down so a
    future ladder redesign cannot quietly introduce leverage without an explicit exemption.
    """

    def test_ssi_above_one_never_raises_the_ceiling(self) -> None:
        runic = {
            "variables_dashboard": [
                {"variable": "VIX", "current": 12.0, "pctile_3yr": 10.0},
                {"variable": "HY", "current": 2.5, "tier": "REAL"},
            ],
            "regime": {"val_regime": "NORMAL", "geo_overlay": "NEUTRAL"},
        }
        capped = portfolio_svc._compute_ceiling(
            "lowvol", runic, {"ssi_multiplier": 1.20}, spx_trend_mult=1.0, spx_trend_meta={}
        )
        neutral = portfolio_svc._compute_ceiling(
            "lowvol", runic, {"ssi_multiplier": 1.00}, spx_trend_mult=1.0, spx_trend_meta={}
        )
        self.assertEqual(capped["ssi_multiplier"], 1.0)
        self.assertEqual(capped["ssi_multiplier_raw"], 1.20)
        self.assertEqual(capped["final_ceiling_pct"], neutral["final_ceiling_pct"])

    def test_ceiling_cannot_exceed_one_hundred_percent(self) -> None:
        runic = {
            "variables_dashboard": [
                {"variable": "VIX", "current": 10.0, "pctile_3yr": 1.0},
                {"variable": "HY", "current": 1.0, "tier": "REAL"},
            ],
            "regime": {},
        }
        for ssi in (1.0, 1.2, 5.0):
            ceiling = portfolio_svc._compute_ceiling(
                "lowvol", runic, {"ssi_multiplier": ssi}, spx_trend_mult=1.0, spx_trend_meta={}
            )
            self.assertLessEqual(
                ceiling["final_ceiling_pct"], 100.0, f"ceiling breached 100% at SSI {ssi}"
            )

    def test_ssi_below_one_still_cuts_the_ceiling(self) -> None:
        """The cap must not neuter the haircut direction — only the upside."""
        runic = {
            "variables_dashboard": [
                {"variable": "VIX", "current": 12.0, "pctile_3yr": 10.0},
                {"variable": "HY", "current": 2.5, "tier": "REAL"},
            ],
            "regime": {},
        }
        haircut = portfolio_svc._compute_ceiling(
            "lowvol", runic, {"ssi_multiplier": 0.80}, spx_trend_mult=1.0, spx_trend_meta={}
        )
        neutral = portfolio_svc._compute_ceiling(
            "lowvol", runic, {"ssi_multiplier": 1.00}, spx_trend_mult=1.0, spx_trend_meta={}
        )
        self.assertLess(haircut["final_ceiling_pct"], neutral["final_ceiling_pct"])

    def test_ssi_ceiling_step_is_labelled_distinctly_from_the_raw_multiplier(self) -> None:
        """One number under two meanings was the 1.00x-vs-1.20x panel mismatch."""
        runic = {
            "variables_dashboard": [
                {"variable": "VIX", "current": 12.0, "pctile_3yr": 10.0},
                {"variable": "HY", "current": 2.5, "tier": "REAL"},
            ],
            "regime": {},
        }
        ceiling = portfolio_svc._compute_ceiling(
            "lowvol", runic, {"ssi_multiplier": 1.20}, spx_trend_mult=1.0, spx_trend_meta={}
        )
        step = next(s for s in ceiling["steps"] if "SSI" in s["label"])
        self.assertIn("capped", step["label"].lower())
        self.assertEqual(step["value"], "×1.00")
        self.assertEqual(step["raw_value"], "×1.20")


