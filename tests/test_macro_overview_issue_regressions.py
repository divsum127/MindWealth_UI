"""Regression tests for Rohit's 13 Sep 2026 Macro Runic overview findings."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from api.services import macro_service
from src.macro_intelligence.engine.combo_detector import detect_named_combos, evaluate_combo_f_window
from src.macro_intelligence.output.briefing_renderer import build_system_recommendation
from tests.api_test_helpers import disable_rate_limits


def _runic_snapshot() -> dict:
    return {
        "date": "2026-09-14",
        "dominant_signal": "F",
        "brave_fearful": "TACTICAL_EASY_MONEY",
        "brave_fearful_display": "TACTICAL EASY MONEY",
        "active_combos": [
            {
                "combo": "F",
                "status": "ACTIVE",
                "duration_weeks": 24,
                "duration_bucket": "LONG",
                "hit_rate_3m": 0.80,
            },
            {
                "combo": "C",
                "status": "ACTIVE",
                "duration_weeks": 2,
                "duration_bucket": "SHORT",
            },
        ],
        "watch_combos": [
            {
                "combo": "E",
                "status": "WATCH",
                "legs_confirmed": 2,
                "total_legs": 3,
                "confirmed_legs": ["CAPE", "NFCI"],
                "pending": "CFTC",
            }
        ],
        "combo_status_rows": [
            {
                "combo": "E",
                "status": "WATCH 2/3",
                "confirmed_legs": ["CAPE", "NFCI"],
                "legs_confirmed": 2,
                "total_legs": 3,
                "pending": "CFTC",
            }
        ],
        "variables_dashboard": [
            {"variable": "CAPE", "current": 41.41, "tier": "EXTREME"},
            {"variable": "NFCI", "current": -0.564, "tier": "NORMAL"},
            {"variable": "CFTC", "current": -362086.9, "pctile_3yr": 37.82, "tier": "NORMAL"},
            {"variable": "WTI", "current": 20.25, "tier": "EXTREME"},
        ],
        "combo_f_active": True,
        "combo_f_weeks_elapsed": 24,
        "combo_f_status": "ACTIVE",
        "ssi_layer2_status": "PARTIAL",
        "ssi_multiplier": 1.0,
        "combo_c_cancel": {
            "active": True,
            "wti_potential_week": 0,
            "wti_leg_ok": False,
            "model_cancel_prob": 0.05,
            "model_wti_leg_prob": 0.08,
            "model_cpi_leg_prob": 0.625,
            "model_sigma": 0.61,
            "model_sigma_source": "ovx_implied",
            "model_sigma_as_of": "2026-09-11",
            "model_weeks_remaining": 4,
            "model_weeks_banked": 0,
            "model_cpi_prints_in_window": 1,
            "model_cpi_n_obs": 84,
        },
    }


def test_status_bar_returns_render_safe_ids_and_separate_details() -> None:
    with patch.object(macro_service, "_load_runic", return_value=_runic_snapshot()):
        body = macro_service.get_status_bar()

    assert body["active_combos"] == ["F", "C"]
    assert body["watch_combos"] == ["E"]
    assert body["watch_combo_details"][0]["confirmed_legs"] == ["CAPE", "NFCI"]
    assert body["watch_combo_details"][0]["unmet_legs"] == ["CFTC"]


def test_http_overview_contract_is_render_safe_and_keeps_watch_state() -> None:
    disable_rate_limits()
    client = TestClient(app)
    with (
        patch.object(macro_service, "_load_runic", return_value=_runic_snapshot()),
        patch(
            "src.macro_intelligence.output.json_writer.read_positioning_data",
            return_value={},
        ),
    ):
        status_response = client.get("/api/v1/macro/status")
        overview_response = client.get("/api/v1/macro/overview/kpis")

    assert status_response.status_code == 200
    assert status_response.json()["watch_combos"] == ["E"]
    assert status_response.json()["watch_combo_details"][0]["legs_confirmed"] == 2
    assert overview_response.status_code == 200
    assert overview_response.json()["cape"]["combo_e_status"] == "WATCH 2/3"
    assert overview_response.json()["simultaneous_active_combos"][0]["combo"] == "C"


def test_overview_preserves_e_watch_and_surfaces_secondary_active_combo() -> None:
    with patch.object(macro_service, "_load_runic", return_value=_runic_snapshot()):
        body = macro_service.get_overview_kpis()

    assert body["simultaneous_active_combos"] == [
        {"combo": "C", "status": "ACTIVE", "duration_weeks": 2, "duration_bucket": "SHORT"}
    ]
    assert body["cape"]["combo_e_status"] == "WATCH 2/3"
    assert body["combo_e"] == {
        "combo": "E",
        "status": "WATCH 2/3",
        "is_active": False,
        "is_watch": True,
        "legs_confirmed": 2,
        "total_legs": 3,
        "confirmed_legs": ["CAPE", "NFCI"],
        "unmet_legs": ["CFTC"],
        "leg_values": {
            "CAPE": {"value": 41.41, "threshold": ">=32", "passes": True},
            "NFCI": {"value": -0.564, "threshold": "<=-0.15", "passes": True},
            "CFTC": {"value": 37.82, "threshold": ">=85th percentile", "passes": False},
        },
    }


def test_recommendation_names_active_c_and_defines_sigma() -> None:
    snapshot = _runic_snapshot()
    snapshot["system_recommendation"] = (
        "TACTICAL EASY MONEY — Combo F recovery window active. "
        "Respect Combo C if also active; sigma 61%."
    )
    recommendation = build_system_recommendation(snapshot)

    assert "Combo C ACTIVE (week 2, SHORT)" in recommendation
    assert "if also active" not in recommendation
    assert "WTI annualised implied volatility 61% from OVX" in recommendation
    assert "model P(cancel next 4wk)=5%" in recommendation


def test_recommendation_labels_realised_sigma_as_realised_not_implied() -> None:
    snapshot = _runic_snapshot()
    snapshot["combo_c_cancel"]["model_sigma_source"] = "realised_60d"

    recommendation = build_system_recommendation(snapshot)

    assert "WTI annualised realised volatility 61% from 60d realised returns" in recommendation
    assert "implied volatility 61%" not in recommendation


def test_regime_and_narrative_endpoints_do_not_serve_stale_recommendation_text() -> None:
    snapshot = _runic_snapshot()
    snapshot["system_recommendation"] = "Respect Combo C if also active; sigma 61%."
    with (
        patch.object(macro_service, "_load_runic", return_value=snapshot),
        patch(
            "src.macro_intelligence.output.json_writer.read_positioning_data",
            return_value={},
        ),
    ):
        regime = macro_service.get_regime()
        narrative = macro_service.get_narrative()

    assert "Combo C ACTIVE (week 2, SHORT)" in regime["system_recommendation"]
    assert "Combo C ACTIVE (week 2, SHORT)" in narrative["system_recommendation"]
    assert "if also active" not in regime["system_recommendation"]


def test_cancel_tracker_exposes_sigma_definition_and_model_components() -> None:
    with (
        patch.object(macro_service, "_load_runic", return_value=_runic_snapshot()),
        patch.object(macro_service, "_db_combo_c_cancel", return_value={}),
        patch.object(macro_service, "_db_friday_cancel_log", return_value=[]),
        patch.object(macro_service, "_db_latest_cpi_print", return_value=None),
        patch.object(macro_service, "_db_upcoming_releases", return_value=[]),
    ):
        body = macro_service.get_combo_c_cancel_tracker()

    model = body["probability_model"]
    assert model["cancel_probability"] == 0.05
    assert model["sigma"] == 0.61
    assert model["sigma_unit"] == "annualised_decimal"
    assert model["sigma_display"] == "61%"
    assert model["sigma_source"] == "OVX WTI option-implied volatility"
    assert model["sigma_as_of"] == "2026-09-11"
    assert model["weeks_remaining"] == 4
    assert model["cpi_sample_size"] == 84


def test_partial_ssi_is_explained_as_contested_not_incomplete() -> None:
    positioning = {
        "layer2_status": "PARTIAL",
        "layer2_confirmed_count": 5,
        "ssi_multiplier": 1.0,
        "layer2_gate_direction": "CONTESTED",
        "layer2_gate_label": "L2: 2 long / 3 short of 6 - contested",
        "inputs": {
            "layer2_gate_conf_long": 2,
            "layer2_gate_conf_short": 3,
            "layer2_gate_votes": [{"vote": True}] * 5 + [{"vote": False}],
        },
    }

    detail = macro_service.build_ssi_layer2_display(positioning)

    assert detail["display_status"] == "CONTESTED"
    assert detail["confirmed_votes"] == 5
    assert detail["long_votes"] == 2
    assert detail["short_votes"] == 3
    assert detail["neutral_votes"] == 1
    assert detail["multiplier"] == 1.0
    assert detail["explanation"] == "Both bullish and bearish sides are confirmed, so sizing stays neutral at 1.00x."


def test_overview_exposes_the_contested_ssi_vote_breakdown() -> None:
    positioning = {
        "layer2_status": "PARTIAL",
        "layer2_confirmed_count": 5,
        "ssi_multiplier": 1.0,
        "layer2_gate_direction": "CONTESTED",
        "layer2_gate_label": "L2: 2 long / 3 short of 6 - contested",
        "inputs": {
            "layer2_gate_conf_long": 2,
            "layer2_gate_conf_short": 3,
            "layer2_gate_votes": [{"vote": True}] * 5 + [{"vote": False}],
        },
    }
    with (
        patch.object(macro_service, "_load_runic", return_value=_runic_snapshot()),
        patch(
            "src.macro_intelligence.output.json_writer.read_positioning_data",
            return_value=positioning,
        ),
    ):
        body = macro_service.get_overview_kpis()

    assert body["ssi_layer2"]["display_status"] == "CONTESTED"
    assert body["ssi_layer2"]["long_votes"] == 2
    assert body["ssi_layer2"]["short_votes"] == 3
    assert body["ssi_layer2"]["neutral_votes"] == 1
    assert body["ssi_layer2"]["multiplier"] == 1.0


def test_combo_f_window_is_active_through_week_26_then_expires() -> None:
    week_26 = evaluate_combo_f_window(
        above_50wma=True,
        entry_gate_passes=True,
        episode_weeks=26,
        max_weeks=26,
    )
    week_27 = evaluate_combo_f_window(
        above_50wma=True,
        entry_gate_passes=True,
        episode_weeks=27,
        max_weeks=26,
    )

    assert week_26 == {"status": "ACTIVE", "active": True, "week": 26}
    assert week_27 == {"status": "EXPIRED", "active": False, "week": 27}


def test_combo_f_does_not_restart_without_a_new_episode() -> None:
    expired = evaluate_combo_f_window(
        above_50wma=True,
        entry_gate_passes=True,
        episode_weeks=31,
        max_weeks=26,
    )
    fresh = evaluate_combo_f_window(
        above_50wma=True,
        entry_gate_passes=True,
        episode_weeks=None,
        max_weeks=26,
    )
    invalidated = evaluate_combo_f_window(
        above_50wma=False,
        entry_gate_passes=True,
        episode_weeks=8,
        max_weeks=26,
    )

    assert expired["status"] == "EXPIRED"
    assert expired["active"] is False
    assert fresh == {"status": "ACTIVE", "active": True, "week": 1}
    assert invalidated == {"status": "INVALIDATED", "active": False, "week": 8}


def test_named_combo_detector_does_not_emit_f_after_expiry() -> None:
    spx = pd.DataFrame(
        {
            "close": [106.0, 107.0],
            "wma50": [100.0, 100.0],
            "above_50wma": [True, True],
        },
        index=pd.to_datetime(["2026-09-04", "2026-09-11"]),
    )
    readings = {
        "CFTC": {
            "raw_value": -100000.0,
            "unconditional_pctile": 40.0,
            "pctile_rank_3yr": 40.0,
        }
    }
    with (
        patch(
            "src.macro_intelligence.engine.combo_detector.load_all_series",
            return_value={"SPX_W": spx},
        ),
        patch(
            "src.macro_intelligence.engine.combo_detector._combo_f_weeks",
            return_value=27,
        ),
    ):
        fires = detect_named_combos("2026-09-11", readings=readings)

    assert not any(fire.runic_combo == "F" for fire in fires)


def test_combo_f_tracker_explains_expiry_without_creating_an_exit_signal() -> None:
    snapshot = _runic_snapshot()
    snapshot.update(
        {
            "date": "2026-10-10",
            "active_combos": [],
            "combo_f_active": False,
            "combo_f_weeks_elapsed": 28,
            "combo_f_status": "EXPIRED",
            "combo_f_episode_start": "2026-04-03",
        }
    )
    with (
        patch.object(macro_service, "_load_runic", return_value=snapshot),
        patch.object(macro_service, "_db_combo_fire_detail", return_value={"date": "2026-04-03"}),
        patch.object(macro_service, "_db_analog_details", return_value=[]),
        patch(
            "src.macro_intelligence.engine.combo_metadata.combo_hit_rate_stats",
            return_value={"hit_rate_primary": 0.80, "avg_return_primary": 5.6},
        ),
    ):
        body = macro_service.get_combo_f_window()

    assert body["lifecycle_status"] == "EXPIRED"
    assert body["active"] is False
    assert body["weeks_elapsed"] == 28
    assert body["window_message"] == (
        "Combo F window completed. It is no longer a fresh tactical tailwind; "
        "this is not an automatic portfolio exit."
    )


def test_combo_status_table_marks_completed_f_window_expired() -> None:
    from src.macro_intelligence.output.briefing_renderer import build_combo_status_rows

    snapshot = _runic_snapshot()
    snapshot.update(
        {
            "active_combos": [snapshot["active_combos"][1]],
            "combo_f_active": False,
            "combo_f_status": "EXPIRED",
            "combo_f_episode_start": "2026-04-03",
        }
    )
    with patch(
        "src.macro_intelligence.output.briefing_renderer._all_time_combo_stats",
        return_value={},
    ):
        rows = build_combo_status_rows(snapshot)

    f_row = next(row for row in rows if row["combo"] == "F")
    assert f_row["status"] == "EXPIRED"
    assert f_row["duration"] == "26-week recovery window completed · started 2026-04-03"


def test_combo_e_watch_calls_cftc_unmet_not_pending_data() -> None:
    from src.macro_intelligence.output.briefing_renderer import build_combo_status_rows

    with patch(
        "src.macro_intelligence.output.briefing_renderer._all_time_combo_stats",
        return_value={},
    ):
        rows = build_combo_status_rows(_runic_snapshot())

    e_row = next(row for row in rows if row["combo"] == "E")
    assert e_row["status"] == "WATCH 2/3"
    assert "not met CFTC" in e_row["duration"]
    assert "pending CFTC" not in e_row["duration"]


def test_combo_cards_use_correct_copy_evidence_and_pending_semantics() -> None:
    snapshot = _runic_snapshot()
    with patch.object(macro_service, "_load_runic", return_value=snapshot):
        body = macro_service.get_all_combos()

    cards = {card["combo"]: card for card in body["combos"]}
    assert cards["A"]["direction"] == "EASY MONEY OR TIGHT MONEY"
    assert "CPI surprise >=+0.2pp" in cards["C"]["description"]
    assert "never fires Combo C" in cards["C"]["description"]
    assert cards["B"]["hit_rate_primary"] == 0.748
    assert cards["B"]["evidence"]["n"] == 274
    assert cards["D"]["hit_rate_primary"] == 0.5652
    assert cards["D"]["evidence"]["n"] == 46
    assert cards["D"]["evidence"]["primary_horizon"] == "1W"
    assert cards["D"]["evidence"]["secondary_horizon"] == "2W"
    assert cards["D"]["evidence"]["secondary_hit_rate"] == 0.4348
    assert "43.5% hit at 2W" in cards["D"]["description"]
    assert cards["E"]["evidence"]["status"] == "PENDING"
    assert cards["E"]["hit_rate_primary"] is None
    assert cards["E"]["pending_data"] == []
    assert cards["E"]["unmet_legs"] == ["CFTC"]
