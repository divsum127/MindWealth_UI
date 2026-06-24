#!/usr/bin/env python3
"""Backfill named combo fires (A–G) for historical Fridays without generic 298-combo bloat."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.pull_all import get_readings_as_of, load_all_series
from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.db.migrate import migrate_db
from src.macro_intelligence.engine.combo_detector import detect_named_combos
from src.macro_intelligence.engine.forward_returns import backfill_forward_returns
from src.macro_intelligence.engine.regime_rules import build_python_regime
from src.macro_intelligence.models import ComboFire

# Documented Combo C analog episodes (WTI/CPI history may be absent in daily_readings).
COMBO_C_SEED_DATES = ("2008-06-16", "2022-06-09", "2025-04-14")


def _fridays(start: datetime, end: datetime) -> list[str]:
    cur = start
    out: list[str] = []
    while cur <= end:
        if cur.weekday() == 4:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def _persist_if_new(fires: list[ComboFire]) -> int:
    added = 0
    with get_connection() as conn:
        for f in fires:
            if not f.runic_combo:
                continue
            row = conn.execute(
                """
                SELECT 1 FROM combo_fires
                WHERE date = ? AND runic_combo = ? AND status = ?
                LIMIT 1
                """,
                (f.date, f.runic_combo, f.status),
            ).fetchone()
            if row:
                continue
            conn.execute(
                """
                INSERT INTO combo_fires
                (date, var1_id, var2_id, var3_id, var1_direction, var2_direction, var3_direction,
                 runic_combo, status, duration_weeks, duration_bucket, gate_flag, macro_regime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f.date,
                    f.var_ids[0] if len(f.var_ids) > 0 else None,
                    f.var_ids[1] if len(f.var_ids) > 1 else None,
                    f.var_ids[2] if len(f.var_ids) > 2 else None,
                    f.directions[0] if len(f.directions) > 0 else None,
                    f.directions[1] if len(f.directions) > 1 else None,
                    f.directions[2] if len(f.directions) > 2 else None,
                    f.runic_combo,
                    f.status,
                    f.duration_weeks,
                    f.duration_bucket.value if f.duration_bucket else None,
                    f.gate_flag.value,
                    json.dumps(f.macro_regime) if f.macro_regime else None,
                ),
            )
            added += 1
        conn.commit()
    return added


def _seed_combo_c_fires() -> int:
    """Insert documented Combo C analog dates when detection cannot reach historical CPI/WTI."""
    added = 0
    with get_connection() as conn:
        for ds in COMBO_C_SEED_DATES:
            row = conn.execute(
                "SELECT 1 FROM combo_fires WHERE date = ? AND runic_combo = 'C' LIMIT 1",
                (ds,),
            ).fetchone()
            if row:
                continue
            conn.execute(
                """
                INSERT INTO combo_fires
                (date, var1_id, var2_id, var3_id, runic_combo, status, gate_flag, macro_regime)
                VALUES (?, 'WTI', 'CPI', 'WALCL', 'C', 'ACTIVE', 'SIGNAL', ?)
                """,
                (ds, json.dumps({"seed": "documented_analog"})),
            )
            added += 1
        conn.commit()
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill named combo A–G fires")
    parser.add_argument("--from", dest="from_date", default="2006-01-06")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--limit", type=int, default=0, help="Max Fridays to process")
    parser.add_argument("--skip-forward-returns", action="store_true")
    args = parser.parse_args()

    init_db()
    migrate_db()
    load_all_series(force=True)

    end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
    start = datetime.strptime(args.from_date, "%Y-%m-%d")
    dates = _fridays(start, end)
    if args.limit:
        dates = dates[: args.limit]

    total_added = 0
    for i, ds in enumerate(dates, 1):
        try:
            readings = get_readings_as_of(ds)
            regime = build_python_regime(ds, readings)
            fires = detect_named_combos(ds, readings, macro_regime=regime)
            total_added += _persist_if_new(fires)
        except Exception as exc:
            print(f"  WARN skip {ds}: {exc}", flush=True)
        if i % 100 == 0:
            print(f"  ... {i}/{len(dates)} Fridays ({ds}), new fires: {total_added}", flush=True)

    seeded_c = _seed_combo_c_fires()
    if seeded_c:
        print(f"Seeded {seeded_c} documented Combo C analog fires", flush=True)
        total_added += seeded_c

    print(f"Named combo backfill: {len(dates)} Fridays scanned, {total_added} new rows inserted", flush=True)

    if not args.skip_forward_returns:
        print("Filling SPX forward returns...", flush=True)
        filled = backfill_forward_returns()
        print(f"Forward returns updated: {filled} rows", flush=True)

    with get_connection() as conn:
        for letter in "ABCDEFG":
            n = conn.execute(
                "SELECT COUNT(*) FROM combo_fires WHERE runic_combo = ?", (letter,)
            ).fetchone()[0]
            mature_c = None
            if letter == "C":
                mature_c = conn.execute(
                    """
                    SELECT COUNT(*) FROM combo_fires cf
                    JOIN forward_returns fr ON cf.combo_id = fr.combo_id
                    WHERE cf.runic_combo = 'C' AND fr.spx_6m IS NOT NULL
                    """
                ).fetchone()[0]
            extra = f", mature 6M returns: {mature_c}" if mature_c is not None else ""
            print(f"  Combo {letter}: {n} fires{extra}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
