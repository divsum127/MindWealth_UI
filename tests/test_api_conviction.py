"""API tests for Conviction Engine routes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from api.services import conviction_service
from tests.api_test_helpers import disable_rate_limits


class TestHealthAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)
        self._api_patch = patch.dict("os.environ", {"API_KEY": ""}, clear=False)
        self._key_patch = patch("api.dependencies.API_KEY", "")
        self._api_patch.start()
        self._key_patch.start()

    def tearDown(self) -> None:
        self._key_patch.stop()
        self._api_patch.stop()

    def test_health_ok(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("version", body)
        self.assertIn("conviction_store", body)


class TestConvictionReadAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)

    def test_list_overlay_dates(self) -> None:
        response = self.client.get("/api/v1/conviction/overlays/dates")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_list_tickers(self) -> None:
        response = self.client.get("/api/v1/conviction/tickers?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_ticker_not_found(self) -> None:
        response = self.client.get("/api/v1/conviction/tickers/ZZZZNOTICKER999")
        self.assertEqual(response.status_code, 404)

    def test_get_engine_audit_route(self) -> None:
        fake = {
            "policies": {
                "dividend_scoring_rollout_requires_approval": True,
                "dividend_penalty_requires_explicit_approval": True,
            },
            "summary": {"total_records": 0},
            "records": [],
        }
        with patch(
            "api.services.conviction_service.get_engine_audit",
            return_value=fake,
        ):
            response = self.client.get("/api/v1/conviction/audit")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.json()["policies"]["dividend_penalty_requires_explicit_approval"]
        )
        self.assertTrue(
            response.json()["policies"]["dividend_scoring_rollout_requires_approval"]
        )

    def test_engine_audit_distinguishes_fixed_and_legacy_state(self) -> None:
        records = [
            {
                "ticker": "FIXED",
                "asset_type": "EQUITY",
                "conviction_score": 0,
                "business_type": "compounder",
                "bq_components": {"ceo_quality": 0, "competitive_moat": 0},
                "dividend_cut_flag": {"triggered": True, "decline_pct": 0.25},
                "dividend_cut_penalty_applied": False,
                "dividend_cut_penalty_pending_approval": True,
                "agent_dims_status": "ran",
                "agent_dim_provenance": {
                    "ceo_quality": {
                        "source": "agent",
                        "reported_confidence": 0.8,
                        "confidence": 0.55,
                        "confidence_caps_applied": [
                            {"rule": "opposing_evidence_text_longer", "cap": 0.55}
                        ],
                        "sources": ["one", "two"],
                        "evidence_for": "support",
                        "evidence_against": "counter evidence",
                    },
                },
                "agent_run_usage": {
                    "model": "test-model",
                    "dimension_calls": 5,
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "web_search_requests": 5,
                },
                "framework_coverage": False,
                "framework_coverage_capped": True,
                "pe_20y_array": [10, 11],
                "pe_history_meta": {
                    "years_available": 12,
                    "point_count": 2,
                    "target_years": 20,
                },
                "statement_coverage": {
                    "quarterly_income_empty": False,
                    "cashflow_prior_year_available": True,
                },
            },
            {
                "ticker": "LEGACY",
                "asset_type": "EQUITY",
                "conviction_score": 1,
                "business_type": "compounder",
            },
        ]
        with patch.object(conviction_service, "list_records", return_value=records):
            audit = conviction_service.get_engine_audit()

        self.assertEqual(audit["summary"]["total_records"], 2)
        self.assertEqual(audit["summary"]["dividend_pending_approval"], 1)
        self.assertEqual(audit["summary"]["dividend_gate_not_recorded"], 1)
        self.assertEqual(audit["summary"]["low_confidence_neutralized"], 1)
        self.assertEqual(audit["summary"]["framework_capped"], 1)
        fixed, legacy = audit["records"]
        self.assertEqual(fixed["pe_history_band"], "10_to_15")
        self.assertEqual(fixed["dividend_verification_status"], "candidate_unverified")
        self.assertEqual(audit["summary"]["dividend_candidates_unverified"], 1)
        self.assertEqual(audit["summary"]["pe_10_to_15"], 1)
        self.assertEqual(audit["summary"]["pe_no_series"], 1)
        confidence = fixed["agent_confidence_details"][0]
        self.assertEqual(confidence["reported_confidence"], 0.8)
        self.assertEqual(confidence["final_confidence"], 0.55)
        self.assertEqual(confidence["source_count"], 2)
        self.assertTrue(confidence["neutralized"])
        self.assertEqual(fixed["quarterly_income_status"], "available")
        self.assertEqual(legacy["dividend_status"], "not_recorded")
        self.assertIn("dividend rollout state", legacy["legacy_audit_note"])
        self.assertEqual(legacy["quarterly_income_status"], "not_recorded")

    def test_pe_history_audit_bands_match_requested_breaks(self) -> None:
        cases = (
            (20.0, True, "20_plus"),
            (15.0, True, "15_to_20"),
            (10.0, True, "10_to_15"),
            (5.0, True, "5_to_10"),
            (4.99, True, "under_5"),
            (25.0, False, "no_series"),
        )
        for years, has_series, expected in cases:
            with self.subTest(years=years, has_series=has_series):
                self.assertEqual(
                    conviction_service._pe_history_band(years, has_series), expected
                )


class TestConvictionEvaluateAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)

    def test_evaluate_signal_validation_error(self) -> None:
        response = self.client.post("/api/v1/conviction/signals/evaluate", json={})
        self.assertEqual(response.status_code, 422)

    def test_evaluate_signal_with_mock(self) -> None:
        fake = {
            "ticker": "AAPL",
            "original_signal": "BUY",
            "signal_timeframe": "long",
            "verdict": "TACTICAL BUY",
            "sizing_pct": 70.0,
            "conviction_score": 6.0,
            "conviction_raw": 7.0,
            "fs_score": 65.0,
            "fs_class": "moderate_high",
            "yield_trap_warning": False,
            "rationale": "test",
        }
        with patch("api.services.conviction_service.modify_signal") as mock_mod:
            class _FakeMod:
                def to_dict(self) -> dict:
                    return fake

            mock_mod.return_value = _FakeMod()
            response = self.client.post(
                "/api/v1/conviction/signals/evaluate",
                json={
                    "ticker": "AAPL",
                    "technical_signal": "BUY",
                    "signal_timeframe": "long",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verdict"], "TACTICAL BUY")


class TestAPIKey(unittest.TestCase):
    def test_api_key_required_when_set(self) -> None:
        disable_rate_limits()
        with patch.dict("os.environ", {"API_KEY": "test-secret"}, clear=False):
            from importlib import reload

            import api.dependencies as deps

            reload(deps)
            client = TestClient(app)
            response = client.get("/api/v1/health")
            self.assertEqual(response.status_code, 401)
            response = client.get("/api/v1/health", headers={"X-API-Key": "test-secret"})
            self.assertEqual(response.status_code, 200)
            reload(deps)
            import os

            os.environ.pop("API_KEY", None)
            reload(deps)
