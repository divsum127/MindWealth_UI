"""Tests for portfolio API endpoints.

Covers:
  GET  /api/v1/portfolio/sizer
  GET  /api/v1/portfolio/risk
  POST /api/v1/portfolio/risk/analyze
  GET  /api/v1/portfolio/risk/search
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from api.main import app

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
    def test_sizer_pnl_rows_have_names(self, *_mocks) -> None:
        r = client.get("/api/v1/portfolio/sizer")
        pnl_rows = r.json()["pnl_rows"]
        if pnl_rows:
            for row in pnl_rows[:5]:
                self.assertIsNotNone(row.get("name"))
                self.assertNotEqual(row.get("name"), "")
                self.assertEqual(row.get("win_rate_label"), "Backtested Win Rate")


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


if __name__ == "__main__":
    unittest.main()
