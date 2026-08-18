"""Friday EOD job: pull all variables, run combos, persistence, forward returns."""

from __future__ import annotations

from datetime import datetime

from src.macro_intelligence.data.pull_all import pull_all_series
from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.engine.combo_detector import detect_all_combos
from src.macro_intelligence.engine.forward_returns import backfill_forward_returns, fill_matured_returns
from src.macro_intelligence.engine.combo_c_cancel import run_combo_c_cancel_check
from src.macro_intelligence.engine.persistence import run_persistence_scan
from src.macro_intelligence.data.pull_all import get_readings_as_of
from src.macro_intelligence.analysis.regime_experiments.shadow_backfill import (
    update_regime_v2_to_date,
)


def run_friday_pull(as_of: str | None = None) -> dict:
    init_db()
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    readings = pull_all_series(as_of)
    persistence = run_persistence_scan(as_of)
    combos = detect_all_combos(as_of, persist=True)
    filled = fill_matured_returns(as_of)
    backfilled = backfill_forward_returns()
    r = get_readings_as_of(as_of)
    wti = r.get("WTI", {}).get("raw_value")
    c_active = any(c.runic_combo == "C" and c.status == "ACTIVE" for c in combos)
    cancel = run_combo_c_cancel_check(as_of, wti, c_active)

    # macro_regime_log_v2 backs GET /macro/regime/history, the feed Ahil's backtest reads. It
    # had no scheduled writer -- only the manual experiment entrypoint run_all.py -- so it
    # froze at 2026-06-05 while the endpoint kept serving it as current. The table is
    # Friday-evaluated, so this job is where it belongs (2026-08-18).
    regime_rows = update_regime_v2_to_date(as_of)

    return {
        "date": as_of,
        "readings_count": len(readings),
        "persistence_count": len(persistence),
        "combo_fires": len(combos),
        "returns_updated": filled + backfilled,
        "combo_c_cancel": cancel,
        "regime_v2_rows": regime_rows,
    }
