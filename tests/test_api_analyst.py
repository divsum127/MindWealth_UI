"""Tests for AI Analyst / Overwatch API endpoints (v1.8.0)."""

from __future__ import annotations

import os
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

_RUNIC_FIXTURE = {
    "date": "2026-06-18",
    "dominant_signal": "C",
    "dominant_reason": "Combo C active (week 11, MEDIUM).",
    "brave_fearful": "TACTICAL_TIGHT_MONEY",
    "active_combos": [{"combo": "C", "status": "ACTIVE"}],
    "watch_combos": [],
    "narrative": "Tactical tight money backdrop.",
}

_DEGRADATION_FIXTURE = {
    "triggered": True,
    "alerts": [
        {
            "trigger_type": "fwd_degradation",
            "severity": "watch",
            "strategy": "DeltaDrift",
            "combo": {
                "asset": "AAPL",
                "function": "DeltaDrift",
                "interval": "Daily",
                "direction": "Short",
            },
            "bt_rate": 88.0,
            "fwd_rate": 62.5,
            "weekly_trend": [66.0, 64.5, 63.2, 62.5],
            "pattern": "Combo issue",
            "recommendation": "pause new entries",
            "message": "DeltaDrift / Short / Daily: FWD win rate 62.5% — approaching 60% floor.",
            "label": "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION WATCH",
            "border_color": "#ff4d6d",
        }
    ],
    "portfolio_alerts": [],
    "checked_combos": 1,
    "alert_count": 1,
    "floor_pct": 60.0,
    "label": "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION WATCH",
    "border_color": "#ff4d6d",
}


class TestAnalystAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        disable_rate_limits()

    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.services.analyst_service.degrade_svc.check_degradation", return_value=_DEGRADATION_FIXTURE)
    @patch("api.services.analyst_service.macro_svc.get_status_bar")
    @patch("api.services.analyst_service.macro_svc.get_narrative")
    @patch("api.services.analyst_service.macro_svc.get_analog_table")
    def test_analyst_alerts_shape(
        self,
        mock_analog,
        mock_narrative,
        mock_status,
        _mock_deg,
    ) -> None:
        mock_status.return_value = {
            "dominant_signal": "C",
            "active_combos": ["C"],
            "brave_fearful": "TACTICAL_TIGHT_MONEY",
        }
        mock_narrative.return_value = {
            "narrative": "Tactical tight money backdrop.",
            "dominant_reason": "Combo C active",
            "brave_fearful": "TACTICAL_TIGHT_MONEY",
            "date": "2026-06-18",
        }
        mock_analog.return_value = {
            "combo": "C",
            "analog_details": [{"date": "2022-06-09", "spx_3m_pct": -16.0, "regime": {}}],
            "hit_rate_stats": {"hit_rate_primary": 0.8},
        }

        r = self.client.get("/api/v1/analytics/analyst/alerts")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("panel_alerts", body)
        self.assertGreaterEqual(body["count"], 1)
        types = {a["type"] for a in body["panel_alerts"]}
        self.assertIn("degradation", types)
        self.assertIn("runic", types)

        deg = next(a for a in body["panel_alerts"] if a["type"] == "degradation")
        self.assertEqual(deg["id"], "deg-deltadrift-short-daily-aapl")
        self.assertEqual(deg["channel"], "signals")
        self.assertEqual(deg["fwd_trend"], [66.0, 64.5, 63.2, 62.5])
        self.assertIn("signal", deg)
        self.assertEqual(deg["signal"]["fwd_wr"], 62.5)
        self.assertIn("tabs", body["meta"])
        self.assertIn("signals", body["meta"]["tabs"])

    @patch("api.services.analyst_service.degrade_svc.check_degradation", return_value=_DEGRADATION_FIXTURE)
    @patch("api.services.analyst_service.macro_svc.get_ssi_summary")
    @patch("api.services.analyst_service.macro_svc.get_persistence_signals")
    @patch("api.services.analyst_service.macro_svc.get_status_bar")
    @patch("api.services.analyst_service.macro_svc.get_narrative")
    @patch("api.services.analyst_service.macro_svc.get_analog_table")
    @patch("api.services.analyst_service.reports_svc.load_runic_nightly")
    def test_analyst_channel_filter_and_warnings(
        self,
        mock_runic,
        mock_analog,
        mock_narrative,
        mock_status,
        mock_persistence,
        mock_ssi,
        _mock_deg,
    ) -> None:
        mock_runic.return_value = {
            **_RUNIC_FIXTURE,
            "regime": {"val_regime": "EXTREME", "geo_overlay": "REGIONAL_WAR"},
            "variables_dashboard": [{"variable": "CAPE", "current": 42.0}],
            "persistence_signals": [
                {"signal_name": "7WK_GRIND", "var_id": "SPX", "weeks_count": 7, "trigger_value": 0.5}
            ],
        }
        mock_status.return_value = {
            "dominant_signal": "C",
            "active_combos": ["C"],
            "watch_combos": ["B"],
            "brave_fearful": "TACTICAL_TIGHT_MONEY",
        }
        mock_narrative.return_value = {
            "narrative": "Tactical tight money backdrop.",
            "dominant_reason": "Combo C active",
            "brave_fearful": "TACTICAL_TIGHT_MONEY",
            "date": "2026-06-18",
        }
        mock_analog.return_value = {"combo": "C", "analog_details": [], "hit_rate_stats": {}}
        mock_persistence.return_value = {"persistence_signals": []}
        mock_ssi.return_value = {
            "ssi_level": 0.9,
            "posture": "RISK_OFF",
            "short_signal_active": True,
            "long_signal_active": False,
            "layer2_status": "CONFIRMED",
        }

        r = self.client.get("/api/v1/analytics/analyst/alerts?channel=macro")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        types = {a["type"] for a in body["panel_alerts"]}
        self.assertNotIn("degradation", types)
        self.assertIn("regime_warning", types)
        self.assertIn("sentiment_warning", types)
        self.assertIn("runic_watch", types)

    @patch("api.services.analyst_service.get_panel_alerts")
    @patch("api.services.analyst_service.macro_svc.get_regime")
    @patch("api.services.analyst_service.macro_svc.get_ssi_summary")
    @patch("api.services.analyst_service.reports_svc.load_runic_nightly")
    def test_analyst_context_bundle(
        self,
        mock_runic,
        mock_ssi,
        mock_regime,
        mock_alerts,
    ) -> None:
        mock_alerts.return_value = {
            "meta": {
                "floor_pct": 60.0,
                "gap_threshold_pp": 10.0,
                "tabs": {
                    "all": {"count": 1, "badge": "Overwatch · auto-triggered"},
                    "signals": {"count": 0, "badge": "Overwatch · no signal watches"},
                    "macro": {"count": 1, "badge": "Overwatch · Combo C firing"},
                    "system": {"count": 0, "badge": "System monitor · admin only"},
                    "active_combo": "C",
                },
            },
            "count": 1,
            "panel_alerts": [{
                "id": "runic-c",
                "type": "runic",
                "channel": "macro",
                "label": "RUNIC",
                "html": "Combo C",
                "created_at": "2026-06-18T00:00:00Z",
            }],
        }
        mock_regime.return_value = {
            "date": "2026-06-18",
            "regime": {"val_regime": "EXTREME"},
            "dominant_signal": "C",
        }
        mock_ssi.return_value = {"ssi_level": 0.2, "posture": "NEUTRAL"}
        mock_runic.return_value = {
            "regime": {"val_regime": "EXTREME"},
            "variables_dashboard": [{"variable": "CAPE", "current": 42.0}],
        }

        r = self.client.get("/api/v1/analytics/analyst/context")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("regime", body)
        self.assertIn("sentiment", body)
        self.assertTrue(body["chat"]["supports_page_context"])
        self.assertTrue(body["regime"]["macro_override"]["active"])

    @patch("api.services.analyst_service.macro_svc.get_narrative")
    def test_analyst_brief_from_narrative(self, mock_narrative) -> None:
        mock_narrative.return_value = {
            "narrative": "Tactical tight money with strategic easy money backdrop.",
            "date": "2026-06-18",
        }
        r = self.client.get("/api/v1/analytics/analyst/brief")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["source"], "narrative")
        self.assertIn("Tactical tight money", body["snippet"])

    @patch("api.services.system_health_service._check_claude_api")
    @patch("api.services.system_health_service._check_tavily")
    @patch("api.services.system_health_service._check_us_csv_pipeline")
    @patch("api.services.system_health_service._check_india_csv_pipeline")
    @patch("api.services.system_health_service._check_google_sheets_sync")
    @patch("api.services.system_health_service._check_macro_agent")
    @patch("api.services.system_health_service._check_ssi_json_write")
    def test_system_health_requires_admin(
        self,
        *_mocks,
    ) -> None:
        for m in _mocks:
            m.return_value = {"name": "x", "status": "ok", "detail": "ok", "last_success_at": None}

        r = self.client.get("/api/v1/system/health")
        self.assertEqual(r.status_code, 401)

    def test_degradation_watch_vs_breach_logic(self) -> None:
        from api.services import degradation_service as ds

        self.assertTrue(ds._is_declining_toward_floor([65.0, 63.0, 61.5], 60.0))
        self.assertFalse(ds._is_declining_toward_floor([62.0, 61.0, 59.0], 60.0))
        trend = ds._last_n_weekly([70.0, 68.0, 66.0, 64.0], 4)
        self.assertEqual(trend, [70.0, 68.0, 66.0, 64.0])

    @patch("api.services.analyst_service.get_panel_alerts")
    def test_scan_and_publish_dedup(self, mock_panel) -> None:
        from api.services.analyst_service import scan_and_publish_new_alerts

        mock_panel.return_value = {
            "panel_alerts": [
                {
                    "id": "deg-test",
                    "type": "degradation",
                    "html": "test alert",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            first = scan_and_publish_new_alerts(state_path=str(state))
            second = scan_and_publish_new_alerts(state_path=str(state))
            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 0)


if __name__ == "__main__":
    unittest.main()
