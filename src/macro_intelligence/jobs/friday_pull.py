"""Friday EOD job: pull all variables, run combos, persistence, forward returns."""

from __future__ import annotations

from datetime import datetime

from src.macro_intelligence.data.pull_all import pull_all_series
from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.engine.combo_detector import detect_all_combos
from src.macro_intelligence.engine.forward_returns import backfill_forward_returns, fill_matured_returns
from src.macro_intelligence.engine.persistence import run_persistence_scan


def run_friday_pull(as_of: str | None = None) -> dict:
    init_db()
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    readings = pull_all_series(as_of)
    persistence = run_persistence_scan(as_of)
    combos = detect_all_combos(as_of, persist=True)
    filled = fill_matured_returns(as_of)
    backfilled = backfill_forward_returns()
    return {
        "date": as_of,
        "readings_count": len(readings),
        "persistence_count": len(persistence),
        "combo_fires": len(combos),
        "returns_updated": filled + backfilled,
    }
