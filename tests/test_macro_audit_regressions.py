"""Regression coverage for Macro page audit issues MW-010 and MW-011."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from api.services import macro_service
from src.macro_intelligence.data import macro_calendar


def test_mw010_release_boundary_blocks_future_actuals() -> None:
    """An official value cannot exist before the scheduled release timestamp."""
    before = datetime(2026, 10, 14, 8, 29, tzinfo=ZoneInfo("America/New_York"))
    at_release = datetime(2026, 10, 14, 8, 30, tzinfo=ZoneInfo("America/New_York"))

    assert not macro_calendar.release_has_occurred("CPI", "2026-10-14", now=before)
    assert macro_calendar.release_has_occurred("CPI", "2026-10-14", now=at_release)

    pending = macro_calendar.sanitize_release_values(
        "CPI",
        "2026-10-14",
        consensus=0.5,
        actual=0.5,
        now=before,
    )
    released = macro_calendar.sanitize_release_values(
        "CPI",
        "2026-10-14",
        consensus=0.5,
        actual=0.4,
        now=at_release,
    )

    assert pending == {"consensus": 0.5, "actual": None, "surprise_pp": None}
    assert released == {"consensus": 0.5, "actual": 0.4, "surprise_pp": -0.1}


def test_mw010_latest_cpi_query_excludes_future_rows() -> None:
    """The cancel tracker must not promote a poisoned future DB row to latest print."""
    class _Cursor:
        def fetchall(self):
            return []

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, sql: str, params: tuple[str, ...]):
            assert "release_date <= ?" in sql
            assert params == ("2026-09-25",)
            return _Cursor()

    with (
        patch("src.macro_intelligence.db.connection.get_connection", return_value=_Connection()),
        patch.object(macro_service, "_today_et", return_value="2026-09-25"),
    ):
        assert macro_service._db_latest_cpi_print() is None


def test_mw011_combo_c_suppresses_unvalidated_83_percent_claim() -> None:
    """The combo card must use the same primary cohort as detail and analog views."""
    snapshot = {
        "date": "2026-09-25",
        "active_combos": [
            {
                "combo": "C",
                "status": "ACTIVE",
                "duration_weeks": 4,
                "duration_bucket": "SHORT",
            }
        ],
        "watch_combos": [],
        "combo_status_rows": [
            {
                "combo": "C",
                "name": "Stagflation / Energy Shock",
                "status": "ACTIVE",
                "hit_rate_3m": "insufficient episodes",
                "avg_return_3m": "-",
            }
        ],
    }
    stats = {
        "insufficient_episodes": True,
        "min_episodes_required": 5,
        "primary_label": "6M",
        "n_obs_primary": 3,
        "hit_rate_primary": None,
        "avg_return_primary": None,
    }

    with (
        patch.object(macro_service, "_load_runic", return_value=snapshot),
        patch(
            "src.macro_intelligence.engine.combo_metadata.combo_hit_rate_stats",
            return_value=stats,
        ),
    ):
        body = macro_service.get_all_combos()

    combo_c = next(row for row in body["combos"] if row["combo"] == "C")
    assert "83%" not in combo_c["description"]
    assert "6M" in combo_c["description"]
    assert "n=3" in combo_c["description"]
    assert "minimum n=5" in combo_c["description"]
    assert {
        "secondary_horizon", "secondary_n", "secondary_hit_rate",
        "secondary_avg_return", "source", "config_id",
    }.issubset(combo_c["evidence"])
    assert {
        key: combo_c["evidence"][key]
        for key in (
            "primary_horizon", "n", "minimum_n", "status", "hit_rate", "avg_return"
        )
    } == {
        "primary_horizon": "6M",
        "n": 3,
        "minimum_n": 5,
        "status": "INSUFFICIENT HISTORY",
        "hit_rate": None,
        "avg_return": None,
    }
