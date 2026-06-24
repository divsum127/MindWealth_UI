"""Tests for Macro Intelligence API endpoints (v1.3.0)."""

from __future__ import annotations

import json
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

# ─────────────────────────────────────────────────────────────────────────────
# Minimal runic_output.json fixture
# ─────────────────────────────────────────────────────────────────────────────

_RUNIC_FIXTURE: dict = {
    "date": "2026-06-18",
    "regime": {
        "fed_cycle": "CUTTING_EARLY",
        "curve_regime": "STEEPENING",
        "geo_overlay": "REGIONAL_WAR",
        "val_regime": "EXTREME",
        "liquidity": "GLOBAL_EASY",
    },
    "dominant_signal": "C",
    "dominant_reason": (
        "Combo C active (week 11, MEDIUM). 83% 6M hit rate. "
        "Outranks Combo F on configured priority rank. "
        "Bearish medium-duration energy shock dominates tactical bullish recovery signals."
    ),
    "brave_fearful": "TACTICAL_TIGHT_MONEY_STRATEGIC_EASY_MONEY",
    "brave_fearful_display": "TACTICAL TIGHT MONEY / STRATEGIC EASY MONEY",
    "active_combos": [
        {"combo": "C", "status": "ACTIVE", "duration_weeks": 11, "duration_bucket": "MEDIUM",
         "hit_rate_3m": 0.83, "avg_return_3m": -22.0, "confirmed_legs": ["WTI", "CPI", "WALCL"]},
        {"combo": "E", "status": "CONFIRMED", "duration_weeks": None, "duration_bucket": None,
         "confirmed_legs": ["CAPE", "NFCI"]},
        {"combo": "F", "status": "ACTIVE", "duration_weeks": 8, "duration_bucket": None,
         "mtm_pct": 21.8, "episode_start": "2026-03-30"},
    ],
    "watch_combos": [{"combo": "D", "legs_confirmed": 2, "pending": "CFTC"}],
    "persistence_signals": [],
    "generic_combo_watch": [],
    "ssi_multiplier": 1.0,
    "ssi_layer2_status": "CONFIRMED",
    "ssi_positioning_date": "2026-06-14",
    "vix_bypass": False,
    "analog_dates": ["2008-06-16", "2022-06-09"],
    "analog_details": [
        {"date": "2008-06-16", "spx_3m_pct": -28.6, "primary_horizon": "spx_3m",
         "spx_1m_pct": -8.1, "spx_6m_pct": -41.0, "spx_12m_pct": None},
        {"date": "2022-06-09", "spx_3m_pct": -16.0, "primary_horizon": "spx_3m",
         "spx_1m_pct": -8.4, "spx_6m_pct": -12.0, "spx_12m_pct": None},
    ],
    "spx_3m_forward_avg": -22.3,
    "spx_3m_hit_rate": 0.83,
    "combo_f_active": True,
    "combo_f_weeks_elapsed": 8,
    "narrative": "Tactical tight money with strategic easy money backdrop.",
    "variables_dashboard": [
        {"num": 1, "variable": "NFCI", "current": -0.523, "tier": "RARE", "pctile_3yr": 5.0,
         "direction": "DOWN", "source_date": "2026-06-13", "lag_days": 5},
        {"num": 2, "variable": "HY", "current": 305.0, "tier": "NORMAL", "pctile_3yr": 20.0,
         "direction": None, "source_date": "2026-06-17"},
        {"num": 3, "variable": "WALCL", "current": 6700.0, "tier": "NORMAL", "pctile_3yr": 45.0},
        {"num": 4, "variable": "CNH", "current": 7.24, "tier": "NORMAL", "pctile_3yr": 42.0},
        {"num": 5, "variable": "WTI", "current": -17.2, "tier": "WATCH", "pctile_3yr": None},
        {"num": 6, "variable": "VIX", "current": 16.7, "tier": "NORMAL", "pctile_3yr": 22.0},
        {"num": 7, "variable": "VXTS", "current": 1.25, "tier": "EXTREME", "pctile_3yr": None},
        {"num": 8, "variable": "CFTC", "current": None, "tier": "PENDING"},
        {"num": 9, "variable": "CURVE", "current": 43.0, "tier": "NORMAL", "pctile_3yr": 55.0},
        {"num": 10, "variable": "CPI", "current": -0.1, "tier": "NORMAL"},
        {"num": 11, "variable": "GSR", "current": None, "tier": "PENDING"},
        {"num": 12, "variable": "CAPE", "current": 42.04, "tier": "EXTREME", "pctile_3yr": 99.0},
    ],
    "ppi_cooling": True,
    "combo_c_cancel": {
        "wti_potential_week": 0,
        "active": True,
        "cancel_date": None,
        "cancelled": False,
        "model_cancel_prob": 0.18,
        "model_wti_leg_prob": 0.62,
        "model_cpi_leg_prob": 0.52,
    },
    "cftc_status": "PENDING_3DAY_LAG",
    "pending_cpi_release": False,
    "source_freshness": {"last_audit": "2026-06-18"},
    "system_recommendation": "Hold core longs (F wk 8). No new longs (D watch). C MEDIUM active.",
    "regime_grid": [{"dimension": "FED_CYCLE", "value": "CUTTING_EARLY"}],
    "combo_status_rows": [
        {"combo": "C", "status": "ACTIVE", "duration": "wk 11 MEDIUM"},
        {"combo": "E", "status": "CONFIRMED 2/3"},
        {"combo": "F", "status": "ACTIVE wk 8/26"},
        {"combo": "D", "status": "WATCH 2/3 CFTC"},
    ],
}


def _make_mock_service(tmp_json: Path) -> None:
    tmp_json.write_text(json.dumps(_RUNIC_FIXTURE), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────────────────────

class TestMacroAPI(unittest.TestCase):

    def setUp(self) -> None:
        self.client = TestClient(app)
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp_path = Path(self._tmp.name)
        self._tmp.close()
        _make_mock_service(self._tmp_path)
        self._patch = patch("src.config_paths.MACRO_INTEL_JSON_PATH", self._tmp_path)
        self._patch.start()
        # Also patch the service module's import
        import api.services.macro_service as msvc
        import api.services.reports_service as rsvc
        msvc_patch = patch.object(msvc, "_load_runic", lambda: _RUNIC_FIXTURE)
        rsvc_patch = patch.object(rsvc, "load_runic_nightly", lambda: _RUNIC_FIXTURE)
        self._msvc_patch = msvc_patch.start()
        self._rsvc_patch = rsvc_patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        patch.stopall()
        self._tmp_path.unlink(missing_ok=True)

    # ── Legacy endpoints ──────────────────────────────────────────────────────

    def test_runic_nightly(self) -> None:
        r = self.client.get("/api/v1/macro/runic/nightly")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["date"], "2026-06-18")

    def test_runic_variables_current(self) -> None:
        r = self.client.get("/api/v1/macro/runic/variables/current")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("regime", body)
        self.assertIn("variables_dashboard", body)
        self.assertEqual(len(body["variables_dashboard"]), 12)

    def test_combo_active(self) -> None:
        r = self.client.get("/api/v1/macro/combo/active")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["dominant_signal"], "C")
        self.assertIsInstance(body["active_combos"], list)
        self.assertIsInstance(body["watch_combos"], list)

    # ── Status bar ────────────────────────────────────────────────────────────

    def test_status_bar(self) -> None:
        r = self.client.get("/api/v1/macro/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["dominant_signal"], "C")
        self.assertIn("brave_fearful_display", body)
        self.assertIn("active_combos", body)
        self.assertIn("cftc_status", body)
        self.assertIsInstance(body["active_combos"], list)

    # ── KPI cards ─────────────────────────────────────────────────────────────

    def test_overview_kpis(self) -> None:
        r = self.client.get("/api/v1/macro/overview/kpis")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("dominant_signal", body)
        self.assertIn("combo_c_duration", body)
        self.assertIn("combo_f_window", body)
        self.assertIn("cape", body)
        self.assertIn("wti_4wk", body)
        self.assertEqual(body["dominant_signal"]["combo"], "C")
        self.assertEqual(body["combo_c_duration"]["duration_weeks"], 11)
        self.assertEqual(body["combo_f_window"]["weeks_elapsed"], 8)
        self.assertEqual(body["cape"]["current"], 42.04)

    # ── Regime ────────────────────────────────────────────────────────────────

    def test_regime(self) -> None:
        r = self.client.get("/api/v1/macro/regime")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["regime"]["fed_cycle"], "CUTTING_EARLY")
        self.assertEqual(body["regime"]["geo_overlay"], "REGIONAL_WAR")
        self.assertIn("narrative", body)
        self.assertIn("system_recommendation", body)
        self.assertIn("brave_fearful_display", body)

    # ── Variables heatmap ─────────────────────────────────────────────────────

    def test_variables_heatmap(self) -> None:
        r = self.client.get("/api/v1/macro/variables/heatmap")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["variables"]), 12)
        cape = next(v for v in body["variables"] if v["variable"] == "CAPE")
        self.assertEqual(cape["tier"], "EXTREME")
        self.assertIn("rare_gate", cape)
        self.assertIn("extreme_gate", cape)
        self.assertIn("combos", cape)
        self.assertIn("E", cape["combos"])

    def test_heatmap_has_pending(self) -> None:
        r = self.client.get("/api/v1/macro/variables/heatmap")
        body = r.json()
        pending = body["pending_variables"]
        self.assertIn("CFTC", pending)
        self.assertIn("GSR", pending)

    # ── Named combos ─────────────────────────────────────────────────────────

    def test_list_named_combos(self) -> None:
        r = self.client.get("/api/v1/macro/combos")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["combos"]), 7)
        letters = [c["combo"] for c in body["combos"]]
        self.assertEqual(letters, list("ABCDEFG"))

    def test_combo_c_is_active(self) -> None:
        r = self.client.get("/api/v1/macro/combos")
        body = r.json()
        c = next(x for x in body["combos"] if x["combo"] == "C")
        self.assertTrue(c["is_active"])
        self.assertEqual(c["duration_weeks"], 11)

    def test_combo_detail_c(self) -> None:
        with patch("api.services.macro_service._db_combo_fire_detail", return_value=None), \
             patch("api.services.macro_service._db_analog_details", return_value=[]):
            r = self.client.get("/api/v1/macro/combos/C")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["combo"], "C")
        self.assertEqual(body["name"], "Stagflation / Energy Shock")
        self.assertIn("description", body)

    def test_combo_detail_f(self) -> None:
        with patch("api.services.macro_service._db_combo_fire_detail", return_value=None), \
             patch("api.services.macro_service._db_analog_details", return_value=[]):
            r = self.client.get("/api/v1/macro/combos/F")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["combo"], "F")
        self.assertTrue(body["is_active"])

    def test_combo_detail_invalid(self) -> None:
        r = self.client.get("/api/v1/macro/combos/Z")
        self.assertEqual(r.status_code, 400)

    def test_combo_detail_lowercase(self) -> None:
        with patch("api.services.macro_service._db_combo_fire_detail", return_value=None), \
             patch("api.services.macro_service._db_analog_details", return_value=[]):
            r = self.client.get("/api/v1/macro/combos/c")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["combo"], "C")

    # ── Combo C cancel tracker ────────────────────────────────────────────────

    def test_combo_c_cancel_tracker(self) -> None:
        with patch("api.services.macro_service._db_combo_c_cancel",
                   return_value={"wti_potential_week": 0, "active": True, "cancel_date": None,
                                 "cancelled": False, "cpi_leg_passed": True}), \
             patch("api.services.macro_service._db_friday_cancel_log", return_value=[]), \
             patch("api.services.macro_service._db_latest_cpi_print", return_value=None), \
             patch("api.services.macro_service._db_upcoming_releases", return_value=[]):
            r = self.client.get("/api/v1/macro/combo-c/cancel")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("cancel_status", body)
        self.assertEqual(body["cancel_status"]["fridays_required"], 4)
        self.assertIn("current_wti", body)
        self.assertIn("current_cpi", body)
        self.assertIn("probability_model", body)
        self.assertFalse(body["cancel_status"]["cancelled"])

    # ── Combo F window ────────────────────────────────────────────────────────

    def test_combo_f_window(self) -> None:
        with patch("api.services.macro_service._db_combo_fire_detail", return_value=None), \
             patch("api.services.macro_service._db_analog_details", return_value=[]):
            r = self.client.get("/api/v1/macro/combo-f/window")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["active"])
        self.assertEqual(body["weeks_elapsed"], 8)
        self.assertEqual(body["total_weeks"], 26)
        self.assertAlmostEqual(body["progress_pct"], 30.8, delta=1.0)
        self.assertEqual(body["mtm_pct"], 21.8)
        self.assertIn("cancel_condition", body)

    # ── Analog tables ─────────────────────────────────────────────────────────

    def test_analog_table_c(self) -> None:
        analog_rows = [
            {"date": "2008-06-16", "spx_1m_pct": -8.1, "spx_3m_pct": -28.6,
             "spx_6m_pct": -41.0, "spx_9m_pct": None, "spx_12m_pct": None,
             "status": "RESOLVED", "combo": "C", "regime": {}},
            {"date": "2022-06-09", "spx_1m_pct": -8.4, "spx_3m_pct": -16.0,
             "spx_6m_pct": -12.0, "spx_9m_pct": None, "spx_12m_pct": None,
             "status": "RESOLVED", "combo": "C", "regime": {}},
        ]
        with patch("api.services.macro_service._db_analog_details", return_value=analog_rows):
            r = self.client.get("/api/v1/macro/analogs/C")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["combo"], "C")
        self.assertEqual(len(body["analog_details"]), 2)
        self.assertIn("summary_returns", body)

    def test_analog_table_invalid(self) -> None:
        r = self.client.get("/api/v1/macro/analogs/Z")
        self.assertEqual(r.status_code, 400)

    # ── Narrative ─────────────────────────────────────────────────────────────

    def test_narrative(self) -> None:
        r = self.client.get("/api/v1/macro/narrative")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("narrative", body)
        self.assertIn("system_recommendation", body)
        self.assertEqual(body["dominant_signal"], "C")
        self.assertIn("regime", body)

    # ── Persistence ───────────────────────────────────────────────────────────

    def test_persistence(self) -> None:
        r = self.client.get("/api/v1/macro/persistence")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("persistence_signals", body)
        self.assertIn("generic_combo_watch", body)

    # ── Data freshness ────────────────────────────────────────────────────────

    def test_data_freshness(self) -> None:
        r = self.client.get("/api/v1/macro/data/freshness")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["variables_dashboard"]), 12)
        self.assertIn("cftc_status", body)

    # ── Nightly run (dry trigger) ─────────────────────────────────────────────

    def test_trigger_nightly_run(self) -> None:
        mock_result = {
            "date": "2026-06-18",
            "dominant_signal": "C",
            "active_combos": ["C", "E", "F"],
            "watch_combos": ["D"],
            "output_path": "/tmp/runic_output.json",
        }
        with patch("api.services.macro_service.trigger_nightly_run",
                   return_value={**mock_result, "status": "completed"}):
            r = self.client.post("/api/v1/macro/run-nightly",
                                 json={"as_of": "2026-06-18", "use_claude": False})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "completed")


# ─────────────────────────────────────────────────────────────────────────────
# SSI endpoint tests (v1.4.0)
# ─────────────────────────────────────────────────────────────────────────────

_SSI_SUMMARY_MOCK = {
    "date": "2026-06-19",
    "ssi_level": 0.2691,
    "ssi_percentile_5y": 21.7,
    "ssi_multiplier": 1.2,
    "layer2_status": "CONFIRMED",
    "layer2_confirmed_count": 3,
    "layer2_required": 3,
    "posture": "NEUTRAL",
    "long_signal_active": False,
    "short_signal_active": False,
    "inputs": {
        "hyg_lqd":   {"raw": 0.733, "vote": 1, "signal": "RISK_ON", "pctile": 62.3},
        "dbmf_beta": {"raw": 0.263, "vote": 1, "signal": "RISK_ON", "pctile": 58.1},
        "cnn_fg":    {"raw": 37.3,  "vote": 1, "signal": "NEUTRAL",  "pctile": 44.0},
        "vix_ratio": {"raw": 1.16,  "vote": 0, "signal": "RISK_OFF", "pctile": 71.2},
    },
}

_SSI_HISTORY_MOCK = {
    "days_requested": 5,
    "days_available": 5,
    "latest_date": "2026-06-19",
    "latest_level": 0.2691,
    "latest_multiplier": 1.2,
    "series": [
        {
            "date": "2026-06-15", "ssi_level": 0.277,  "ssi_percentile_5y": 22.47,
            "ssi_multiplier": 1.2, "layer2_status": "CONFIRMED", "layer2_confirmed_count": 3,
            "inputs": {"hyg_lqd": 0.733, "dbmf_beta": 0.285, "cnn_fg": 34.0, "vix_ratio": 1.16},
        },
        {
            "date": "2026-06-19", "ssi_level": 0.2691, "ssi_percentile_5y": 21.7,
            "ssi_multiplier": 1.2, "layer2_status": "CONFIRMED", "layer2_confirmed_count": 3,
            "inputs": {"hyg_lqd": 0.733, "dbmf_beta": 0.263, "cnn_fg": 37.3, "vix_ratio": 1.16},
        },
    ],
}

_SSI_MULT_MOCK = {
    "date": "2026-06-19",
    "ssi_multiplier": 1.2,
    "ssi_level": 0.2691,
    "layer2_status": "CONFIRMED",
    "layer2_confirmed_count": 3,
    "long_size_mult": 1.2,
    "short_size_mult": 1.0,
    "long_active": False,
    "short_active": False,
    "long_entry_threshold": -0.6,
    "short_entry_threshold": 0.85,
}


class TestSSIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_ssi_summary_ok(self):
        with patch("api.services.macro_service.get_ssi_summary",
                   return_value=_SSI_SUMMARY_MOCK):
            r = self.client.get("/api/v1/macro/ssi/summary")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("ssi_level", body)
        self.assertIn("ssi_multiplier", body)
        self.assertIn("layer2_status", body)
        self.assertIn("inputs", body)
        self.assertIn("posture", body)

    def test_ssi_summary_fields(self):
        with patch("api.services.macro_service.get_ssi_summary",
                   return_value=_SSI_SUMMARY_MOCK):
            r = self.client.get("/api/v1/macro/ssi/summary")
        body = r.json()
        self.assertEqual(body["ssi_multiplier"], 1.2)
        self.assertEqual(body["layer2_status"], "CONFIRMED")
        self.assertEqual(body["layer2_confirmed_count"], 3)
        self.assertFalse(body["long_signal_active"])
        self.assertFalse(body["short_signal_active"])
        inputs = body["inputs"]
        self.assertIn("hyg_lqd", inputs)
        self.assertIn("dbmf_beta", inputs)
        self.assertIn("cnn_fg", inputs)
        self.assertIn("vix_ratio", inputs)

    def test_ssi_summary_not_found(self):
        with patch("api.services.macro_service.get_ssi_summary",
                   side_effect=FileNotFoundError("No SSI data")):
            r = self.client.get("/api/v1/macro/ssi/summary")
        self.assertEqual(r.status_code, 404)

    def test_ssi_history_default(self):
        with patch("api.services.macro_service.get_ssi_history",
                   return_value=_SSI_HISTORY_MOCK):
            r = self.client.get("/api/v1/macro/ssi/history")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("series", body)
        self.assertIn("days_requested", body)
        self.assertIn("latest_level", body)

    def test_ssi_history_with_days(self):
        with patch("api.services.macro_service.get_ssi_history",
                   return_value=_SSI_HISTORY_MOCK) as mock_fn:
            r = self.client.get("/api/v1/macro/ssi/history?days=5")
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(days=5)

    def test_ssi_history_clamps_max(self):
        """days > 90 should be clamped to 90."""
        with patch("api.services.macro_service.get_ssi_history",
                   return_value=_SSI_HISTORY_MOCK) as mock_fn:
            r = self.client.get("/api/v1/macro/ssi/history?days=999")
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(days=90)

    def test_ssi_history_series_structure(self):
        with patch("api.services.macro_service.get_ssi_history",
                   return_value=_SSI_HISTORY_MOCK):
            r = self.client.get("/api/v1/macro/ssi/history?days=5")
        body = r.json()
        first = body["series"][0]
        self.assertIn("date", first)
        self.assertIn("ssi_level", first)
        self.assertIn("ssi_multiplier", first)
        self.assertIn("inputs", first)

    def test_ssi_multiplier_ok(self):
        with patch("api.services.macro_service.get_ssi_multiplier",
                   return_value=_SSI_MULT_MOCK):
            r = self.client.get("/api/v1/macro/ssi/multiplier")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("ssi_multiplier", body)
        self.assertIn("long_active", body)
        self.assertIn("short_active", body)
        self.assertIn("long_entry_threshold", body)
        self.assertIn("short_entry_threshold", body)

    def test_ssi_multiplier_value(self):
        with patch("api.services.macro_service.get_ssi_multiplier",
                   return_value=_SSI_MULT_MOCK):
            r = self.client.get("/api/v1/macro/ssi/multiplier")
        body = r.json()
        self.assertEqual(body["ssi_multiplier"], 1.2)
        self.assertEqual(body["layer2_status"], "CONFIRMED")

    def test_ssi_multiplier_not_found(self):
        with patch("api.services.macro_service.get_ssi_multiplier",
                   side_effect=FileNotFoundError("No SSI data")):
            r = self.client.get("/api/v1/macro/ssi/multiplier")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
