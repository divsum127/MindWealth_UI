"""Combo C may persist only after a genuine hot-CPI three-leg entry."""

from __future__ import annotations

from unittest.mock import patch

from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.engine.combo_detector import (
    _activate_combo_c_episode,
    _combo_c_episode_start,
    _combo_c_still_active,
)


def test_legacy_active_flag_without_valid_entry_cannot_persist(tmp_path) -> None:
    db = tmp_path / "runic.db"
    init_db(db)
    with patch("src.macro_intelligence.db.connection.db_path", return_value=db):
        with get_connection() as conn:
            conn.execute(
                "UPDATE combo_c_cancel SET active=1, entry_date=NULL WHERE id=1"
            )
        assert _combo_c_still_active() is False
        assert _combo_c_episode_start("2026-09-04") is None


def test_valid_three_leg_entry_records_episode_and_allows_persistence(tmp_path) -> None:
    db = tmp_path / "runic.db"
    init_db(db)
    with patch("src.macro_intelligence.db.connection.db_path", return_value=db):
        _activate_combo_c_episode("2026-09-04")
        assert _combo_c_still_active() is True
        assert _combo_c_episode_start("2026-09-11") == "2026-09-04"
