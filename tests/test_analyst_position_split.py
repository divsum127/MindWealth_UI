"""Position risk must never be reported as a forward win rate.

Portfolio triggers (booked loss, live MTM breach) and forward win-rate drift
used to share one alert type. ``profit_pct`` was coalesced into ``fwd_rate``, so
a position down 23.7% rendered as "FWD WR -23.7%" under a "BELOW 60% FLOOR"
badge. These tests pin the split.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services import analyst_service as svc
from api.services import overwatch_schedule as schedule_svc

_DRIFT_ALERT = {
    "trigger_type": "fwd_drift",
    "severity": "watch",
    "strategy": "TRENDPULSE",
    "combo": {
        "asset": "NFLX",
        "function": "TRENDPULSE",
        "interval": "Daily",
        "direction": "Long",
    },
    "bt_rate": 82.0,
    "fwd_rate": 57.1,
    "weekly_trend": [100.0, 100.0, 0.0, 0.0],
    "pattern": "Function drift",
    "recommendation": "Recalibrate TRENDPULSE parameters.",
    "message": "TRENDPULSE / Long / Daily: FWD win rate 57.1%.",
    "border_color": "#ff4d6d",
}

_MTM_ALERT = {
    "trigger_type": "live_mtm_breach",
    "severity": "breach",
    "side": "short",
    "symbol": "JETS",
    "function": "FRACTAL TRACK",
    "interval": "Daily",
    "direction": "Short",
    "entry_date": "2026-01-05",
    "exit_date": "",
    "profit_pct": -23.70,
    "message": "Live MTM breach on short position: JETS (FRACTAL TRACK/Daily).",
    "recommendation": "Review stop levels.",
    # degradation_service stamps the drift label on these too
    "label": "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DRIFT ALERT BREACH",
    "border_color": "#ff4d6d",
}

# Same combo, different open trades — this is the common case, not an edge one.
_MTM_ALERT_SAME_COMBO = {
    "trigger_type": "live_mtm_breach",
    "severity": "breach",
    "side": "short",
    "symbol": "JETS",
    "function": "FRACTAL TRACK",
    "interval": "Daily",
    "direction": "Short",
    "entry_date": "2026-02-11",
    "exit_date": "",
    "profit_pct": -18.20,
    "message": "Live MTM breach on short position: JETS (FRACTAL TRACK/Daily).",
    "recommendation": "Review stop levels.",
    "border_color": "#ff4d6d",
}

_BOOKED_ALERT = {
    **_MTM_ALERT,
    "trigger_type": "booked_loss",
    "symbol": "SFTBY",
    "side": "long",
    "direction": "Long",
    "entry_date": "2025-11-03",
    "exit_date": "2026-06-30",
    "profit_pct": -10.35,
    "message": "Booked loss on long position: SFTBY.",
}

_DEGRADATION_PAYLOAD = {
    "triggered": True,
    "alerts": [_DRIFT_ALERT],
    "portfolio_alerts": [_MTM_ALERT, _MTM_ALERT_SAME_COMBO, _BOOKED_ALERT],
    "checked_combos": 4,
    "alert_count": 4,
    "floor_pct": 60.0,
}


def _alerts(**kwargs):
    with patch.object(svc.degrade_svc, "check_degradation", return_value=_DEGRADATION_PAYLOAD):
        return svc.get_panel_alerts(include_macro=False, include_sentiment_warnings=False, **kwargs)


class TestPositionRiskSplit(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = _alerts()
        self.alerts = self.payload["panel_alerts"]
        self.by_type = {}
        for a in self.alerts:
            self.by_type.setdefault(a["type"], []).append(a)

    def test_types_are_split(self) -> None:
        self.assertEqual(len(self.by_type.get("degradation", [])), 1)
        self.assertEqual(len(self.by_type.get("position_risk", [])), 3)

    def test_ids_are_unique_across_trades_on_one_combo(self) -> None:
        """One combo commonly holds many open positions at once.

        Keying on function/interval/direction/symbol alone collapsed 29 live
        SFTBY breaches into a single id, which breaks list keys and the
        new-alert diff in the panel.
        """
        ids = [a["id"] for a in self.alerts]
        self.assertEqual(len(set(ids)), len(ids), sorted(ids))

    def test_no_degradation_alert_carries_a_negative_win_rate(self) -> None:
        for alert in self.by_type.get("degradation", []):
            self.assertGreaterEqual(alert["signal"]["fwd_wr"], 0.0, alert["id"])

    def test_position_alerts_have_no_signal_block(self) -> None:
        for alert in self.by_type["position_risk"]:
            self.assertIsNone(alert.get("signal"), alert["id"])
            self.assertIsNotNone(alert.get("position"), alert["id"])

    def test_position_payload_carries_pnl_not_win_rate(self) -> None:
        mtm = next(
            a for a in self.by_type["position_risk"]
            if a["position"]["entry_date"] == "2026-01-05"
        )
        self.assertEqual(mtm["position"]["symbol"], "JETS")
        self.assertEqual(mtm["position"]["profit_pct"], -23.70)
        self.assertEqual(mtm["position"]["floor_pct"], -10.0)

    def test_booked_loss_has_no_mtm_floor(self) -> None:
        booked = next(
            a for a in self.by_type["position_risk"]
            if a["position"]["trigger_type"] == "booked_loss"
        )
        self.assertIsNone(booked["position"]["floor_pct"])

    def test_position_label_is_not_a_drift_label(self) -> None:
        for alert in self.by_type["position_risk"]:
            self.assertNotIn("DRIFT", alert["label"], alert["id"])

    def test_position_alerts_stay_on_the_signals_channel(self) -> None:
        for alert in self.by_type["position_risk"]:
            self.assertEqual(alert["channel"], "signals")

    def test_signals_badge_separates_drift_from_positions(self) -> None:
        badge = self.payload["meta"]["tabs"]["signals"]
        self.assertEqual(badge["drift_count"], 1)
        self.assertEqual(badge["position_count"], 3)
        self.assertIn("1 drift watch", badge["badge"])
        self.assertIn("3 position alerts", badge["badge"])


class TestFloorIsHonoured(unittest.TestCase):
    def test_above_floor_follows_the_requested_floor(self) -> None:
        low = _alerts(floor_pct=50.0)["panel_alerts"]
        high = _alerts(floor_pct=70.0)["panel_alerts"]
        low_drift = next(a for a in low if a["type"] == "degradation")
        high_drift = next(a for a in high if a["type"] == "degradation")
        # fwd_rate is 57.1
        self.assertTrue(low_drift["signal"]["above_floor"])
        self.assertFalse(high_drift["signal"]["above_floor"])


class TestBriefSnippet(unittest.TestCase):
    def test_decimal_does_not_end_the_sentence(self) -> None:
        text = "Combo F is in week 20 and remains dominant with a 78.4% hit rate. Next sentence."
        self.assertEqual(
            svc._first_sentence(text),
            "Combo F is in week 20 and remains dominant with a 78.4% hit rate.",
        )

    def test_text_without_terminator_is_returned_whole(self) -> None:
        self.assertEqual(svc._first_sentence("No terminator"), "No terminator")

    def test_overlong_sentence_is_elided(self) -> None:
        snippet = svc._first_sentence("word " * 100)
        self.assertLessEqual(len(snippet), 221)
        self.assertTrue(snippet.endswith("…"))


class TestScheduleMeta(unittest.TestCase):
    def test_next_scans_are_populated(self) -> None:
        meta = _alerts()["meta"]
        self.assertIsNotNone(meta["next_signal_check"])
        self.assertIsNotNone(meta["next_macro_scan"])

    def test_weekday_schedule_skips_the_weekend(self) -> None:
        friday_evening = datetime(2026, 8, 21, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(
            schedule_svc.next_signal_check(friday_evening), "2026-08-24T19:00:00Z"
        )

    def test_system_scan_lands_on_the_quarter_hour(self) -> None:
        now = datetime(2026, 8, 18, 7, 7, tzinfo=timezone.utc)
        self.assertEqual(schedule_svc.next_system_scan(now), "2026-08-18T07:15:00Z")


if __name__ == "__main__":
    unittest.main()
