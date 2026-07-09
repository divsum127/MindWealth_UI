"""Tests for integration gap API endpoints."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from tests.api_test_helpers import disable_rate_limits


class TestSignalsAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)

    def test_list_reports(self) -> None:
        r = self.client.get("/api/v1/signals/reports")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_shortlist(self) -> None:
        r = self.client.get("/api/v1/signals/shortlist")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("markdown", body)

    def test_latest_new_signals(self) -> None:
        r = self.client.get("/api/v1/signals/reports/new-signals/latest")
        self.assertEqual(r.status_code, 200)
        self.assertIn("records", r.json())


class TestVirtualTradingAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)

    def test_long(self) -> None:
        r = self.client.get("/api/v1/virtual-trading/long")
        self.assertEqual(r.status_code, 200)
        self.assertIn("records", r.json())

    def test_portfolio(self) -> None:
        r = self.client.get("/api/v1/virtual-trading/portfolio")
        self.assertEqual(r.status_code, 200)


class TestAnalyticsAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)

    def test_sigma(self) -> None:
        r = self.client.get("/api/v1/analytics/sigma")
        self.assertEqual(r.status_code, 200)

    def test_sentiment_layers(self) -> None:
        r = self.client.get("/api/v1/analytics/sentiment/layers")
        self.assertEqual(r.status_code, 200)

    def test_portfolio_ytd(self) -> None:
        r = self.client.get("/api/v1/analytics/portfolio-ytd")
        self.assertEqual(r.status_code, 200)
        self.assertIn("forced_portfolio_ytd", r.json())


class TestMacroAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)

    def test_runic_nightly(self) -> None:
        r = self.client.get("/api/v1/macro/runic/nightly")
        if r.status_code == 404:
            self.skipTest("runic output not present")
        self.assertEqual(r.status_code, 200)

    def test_active_combos(self) -> None:
        r = self.client.get("/api/v1/macro/combo/active")
        if r.status_code == 404:
            self.skipTest("runic output not present")
        self.assertEqual(r.status_code, 200)


class TestMonitoredTradesAPI(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "monitored_trades.json"
        self.path.write_text('{"last_updated":"x","trades":[]}', encoding="utf-8")
        patcher = patch("src.utils.monitored_trades.get_monitored_trades_path", return_value=self.path)
        self.patcher = patcher
        self.patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.cleanup()

    def test_list_empty(self) -> None:
        r = self.client.get("/api/v1/monitored-trades")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])


class TestClaudeOverlayFix(unittest.TestCase):
    def test_empty_csv_load(self) -> None:
        from src.conviction_engine.signals import load_signal_file

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"")
            path = f.name
        df = load_signal_file(path)
        self.assertTrue(df.empty)

    def test_overlay_claude_empty(self) -> None:
        from api.services.conviction_service import overlay_signal_file

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"")
            empty_path = Path(f.name)
        with patch("api.services.conviction_service.signal_file_for_report_date", return_value=empty_path):
            r = overlay_signal_file(
                report_date=None,
                report_name="claude_signals_report.csv",
                save_output=False,
                update_layers=False,
            )
        self.assertEqual(r["row_count"], 0)
        self.assertTrue(r.get("csv_empty") or r.get("shortlist"))

    def test_overlay_claude_empty_via_api(self) -> None:
        client = TestClient(app)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"")
            empty_path = Path(f.name)
        with patch("api.services.conviction_service.signal_file_for_report_date", return_value=empty_path):
            r = client.post(
                "/api/v1/conviction/signals/overlay-file",
                json={
                    "report_name": "claude_signals_report.csv",
                    "save_output": False,
                    "update_layers": False,
                },
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["row_count"], 0)
        self.assertTrue(body.get("csv_empty") or body.get("shortlist"))
