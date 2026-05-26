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


class TestHealthAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_ok(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("version", body)
        self.assertIn("conviction_store", body)


class TestConvictionReadAPI(unittest.TestCase):
    def setUp(self) -> None:
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


class TestConvictionEvaluateAPI(unittest.TestCase):
    def setUp(self) -> None:
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
