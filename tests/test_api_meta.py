"""API tests for GET /api/v1/meta."""

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
from api.services.meta_service import market_close_data_updated_at
from tests.api_test_helpers import disable_rate_limits


class TestMarketCloseHelper(unittest.TestCase):
    def test_summer_edt(self) -> None:
        payload = market_close_data_updated_at("2026-07-17")
        self.assertEqual(payload["date"], "2026-07-17")
        self.assertEqual(payload["time"], "16:00:00")
        self.assertEqual(payload["timezone"], "US/Eastern")
        self.assertIn("T16:00:00-04:00", payload["datetime"])

    def test_winter_est(self) -> None:
        payload = market_close_data_updated_at("2026-01-15")
        self.assertIn("T16:00:00-05:00", payload["datetime"])


class TestMetaAPI(unittest.TestCase):
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

    @patch("api.services.meta_service.resolve_report_path")
    @patch("api.services.meta_service.get_data_fetch_datetime")
    def test_meta_prefers_csv_date_over_json(self, mock_fetch, mock_path) -> None:
        mock_fetch.return_value = {
            "date": "2026-07-19",
            "time": "18:00:08",
            "datetime": "2026-07-19 18:00:08",
            "timezone": "US/Eastern",
        }

        def _resolve(name: str, *_args, **_kwargs):
            if name == "outstanding_signal":
                return Path("/trade_store/US/2026-07-17_outstanding_signal.csv")
            return None

        mock_path.side_effect = _resolve

        response = self.client.get("/api/v1/meta")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data_updated_at"]["date"], "2026-07-17")
        self.assertIn("T16:00:00-04:00", body["data_updated_at"]["datetime"])

    @patch("api.services.meta_service.resolve_report_path")
    @patch("api.services.meta_service.get_data_fetch_datetime")
    def test_meta_from_json_when_no_dated_reports(self, mock_fetch, mock_path) -> None:
        mock_fetch.return_value = {
            "date": "2026-07-17",
            "time": "18:00:08",
            "datetime": "2026-07-17 18:00:08",
            "timezone": "US/Eastern",
        }
        mock_path.return_value = None

        response = self.client.get("/api/v1/meta")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data_updated_at"]["date"], "2026-07-17")
        self.assertEqual(body["data_updated_at"]["time"], "16:00:00")
        self.assertIn("T16:00:00-04:00", body["data_updated_at"]["datetime"])
        self.assertEqual(body["data_updated_at"]["timezone"], "US/Eastern")

    @patch("api.services.meta_service.resolve_report_path")
    @patch("api.services.meta_service.get_data_fetch_datetime")
    def test_meta_fallback_filename_when_json_missing(self, mock_fetch, mock_path) -> None:
        mock_fetch.return_value = None
        mock_path.return_value = Path("/trade_store/US/2026-01-15_outstanding_signal.csv")

        response = self.client.get("/api/v1/meta")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data_updated_at"]["date"], "2026-01-15")
        self.assertIn("T16:00:00-05:00", body["data_updated_at"]["datetime"])


if __name__ == "__main__":
    unittest.main()
