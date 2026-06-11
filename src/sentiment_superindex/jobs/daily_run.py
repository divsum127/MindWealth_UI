"""SSI daily job — write positioning.json (~08:00 ET)."""

from __future__ import annotations

from typing import Any

from src.sentiment_superindex.db.connection import init_db, persist_daily
from src.sentiment_superindex.engine.positioning import build_positioning_payload
from src.sentiment_superindex.output.json_writer import write_positioning_json


def run_ssi_daily(as_of: str | None = None) -> dict[str, Any]:
    init_db()
    payload = build_positioning_payload(as_of)
    path = write_positioning_json(payload)
    persist_daily(payload)
    payload["output_path"] = str(path)
    return payload
