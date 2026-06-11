"""macro_regime_log upsert helpers."""

from __future__ import annotations

import json
from typing import Any

from src.macro_intelligence.db.connection import get_connection


def upsert_macro_regime_log(
    date: str,
    regime: dict[str, Any],
    model: str = "python_backfill",
    combo_id: int | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO macro_regime_log (date, combo_id, regime_json, model)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
              regime_json = excluded.regime_json,
              model = excluded.model,
              combo_id = COALESCE(excluded.combo_id, macro_regime_log.combo_id)
            """,
            (date, combo_id, json.dumps(regime), model),
        )


def get_regime_json(date: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT regime_json FROM macro_regime_log WHERE date = ?",
            (date,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["regime_json"])
