#!/usr/bin/env python3
"""Replay the CFTC-leg combo fires after the 2023-05-02 unit restatement, and re-key their returns.

`rebuild_cftc_stored_history.py` repairs stored *values*. It cannot repair stored *decisions*:
`combo_fires` rows were written when a percentile crossed a threshold, and 2,337 of the 4,599
CFTC-leg rows sit on a date whose percentile has since moved (1,080 cross the 15th boundary, 777 the
25th, 115 the 85th). Those rows have to be re-derived, not updated.

**Scope is deliberately CFTC-only.** A probe first checked whether re-detecting a date reproduces the
stored history, and it does not — non-CFTC combos differ on nearly every date, because the stored
history was built by `backfill_named_combo_fires.py` at a point in time and several other series
(HY OAS, CNN F&G, CPI) have been backfilled since. Replaying everything would silently absorb all of
that under the heading of a CFTC fix. So this deletes and re-derives only rows with CFTC as a leg,
and leaves every other row alone. The trade-off is stated rather than hidden: the re-derived CFTC
rows do use today's values for their *other* legs, so not every change is attributable to the unit
fix. The report quantifies how much is, by checking whether the CFTC percentile actually moved on
each changed date.

`forward_returns` is keyed on `combo_fires.combo_id`, which is an autoincrement rowid — deleting and
reinserting a fire produces a new id, so the old return row is orphaned. Returns for the deleted ids
are removed with them and refilled from `backfill_forward_returns()` afterwards.

    python scripts/replay_cftc_combo_fires.py --db macro_intelligence/data/runic.db
    python scripts/replay_cftc_combo_fires.py --db ... --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.pull_all import get_readings_as_of  # noqa: E402
from src.macro_intelligence.engine.combo_detector import (  # noqa: E402
    detect_generic_combos,
    detect_named_combos,
)
from src.macro_intelligence.engine.regime_rules import build_python_regime  # noqa: E402

VAR = "CFTC"


def _is_cftc(var_ids) -> bool:
    return VAR in [v for v in var_ids if v]


def _fire_key(var_ids, runic, status) -> tuple:
    return (tuple(sorted(v for v in var_ids if v)), runic, status)


def detect_cftc_fires(as_of: str) -> list:
    """Named + generic fires for one date, filtered to those with CFTC as a leg."""
    readings = get_readings_as_of(as_of)
    regime = build_python_regime(as_of, readings)
    named = detect_named_combos(as_of, readings, regime)
    named_keys = {tuple(sorted(f.var_ids)) for f in named if f.runic_combo}
    generic = [
        g for g in detect_generic_combos(as_of, readings)
        if tuple(sorted(g.var_ids)) not in named_keys
    ]
    return [f for f in named + generic if _is_cftc(f.var_ids)]


# Every level at which the CFTC percentile changes a decision: the named-combo cuts
# (B <=15, F <=50, E >=85, D >=95) and the tier bands that gate generic combos
# (RARE at 15/85 and 20/80, EXTREME at 5/95). A percentile that moves without crossing one of
# these cannot change a fire, so re-deriving that date would only import drift from other series.
DECISION_BOUNDARIES = (5.0, 15.0, 20.0, 50.0, 80.0, 85.0, 95.0)


def _crosses_boundary(pair: tuple[float, float] | None, min_move: float = 0.01) -> bool:
    if not pair:
        return False
    old, new = pair
    if abs(new - old) <= min_move:
        return False
    lo, hi = (old, new) if old <= new else (new, old)
    return any(lo < b <= hi for b in DECISION_BOUNDARIES)


def _pctile_moves(db: Path, baseline: Path | None = None) -> dict[str, float]:
    """Per-date |change| in CFTC unconditional_pctile between the pre-restatement backup and now.

    Used only for attribution in the report — how much of the combo churn traces to the unit fix
    rather than to other series moving since the original backfill.
    """
    backups = [baseline] if baseline else sorted(db.parent.glob(f"{db.stem}.pre_cftc_restate_*.db"))
    if not backups or backups[0] is None or not Path(backups[0]).exists():
        raise SystemExit(
            "no pre-restatement baseline found. Pass --baseline <runic.pre_cftc_restate_*.db>; "
            "without it every date looks unmoved and the replay silently degrades to a dedupe pass."
        )
    old = pd.read_sql(
        f"SELECT date, unconditional_pctile FROM daily_readings WHERE var_id='{VAR}'",
        sqlite3.connect(backups[0]),
    )
    new = pd.read_sql(
        f"SELECT date, unconditional_pctile FROM daily_readings WHERE var_id='{VAR}'",
        sqlite3.connect(db),
    )
    merged = old.merge(new, on="date", suffixes=("_old", "_new")).dropna()
    return {
        r.date: (float(r.unconditional_pctile_old), float(r.unconditional_pctile_new))
        for r in merged.itertuples()
    }


def replay(
    db: Path,
    *,
    apply: bool,
    limit: int | None = None,
    move_threshold: float = 0.01,
    all_dates: bool = False,
    baseline: Path | None = None,
) -> None:
    """Re-derive CFTC-leg fires.

    By default only dates whose CFTC percentile actually moved are re-derived, plus exact duplicate
    rows are removed everywhere. That restriction exists because re-detection uses *today's* values
    for the other legs, and those have drifted since the fires were written — on recent dates the
    churn is dominated by VIX and CPI, not by CFTC. Rewriting those rows would quietly fold every
    other data change into a commit labelled as a CFTC fix. ``--all-dates`` lifts the restriction
    for anyone who explicitly wants a full recomputation on current data.
    """
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    dates = [r[0] for r in conn.execute("SELECT DISTINCT date FROM combo_fires ORDER BY date")]
    if limit:
        dates = dates[-limit:]
    moves_pair = _pctile_moves(db, baseline)
    print(f"replaying CFTC-leg fires across {len(dates)} dates")

    plan: list[dict] = []
    for i, date in enumerate(dates, 1):
        stored = conn.execute(
            "SELECT combo_id, var1_id, var2_id, var3_id, runic_combo, status FROM combo_fires "
            "WHERE date=? AND (var1_id=? OR var2_id=? OR var3_id=?)",
            (date, VAR, VAR, VAR),
        ).fetchall()
        fresh = detect_cftc_fires(date)
        stored_keys = {_fire_key([r["var1_id"], r["var2_id"], r["var3_id"]], r["runic_combo"], r["status"]) for r in stored}
        fresh_keys = {_fire_key(f.var_ids, f.runic_combo, f.status) for f in fresh}
        moved = _crosses_boundary(moves_pair.get(date), move_threshold)
        has_dupes = len(stored) != len(stored_keys)
        in_scope = all_dates or moved or has_dupes
        if not in_scope:
            if i % 100 == 0:
                print(f"  {i}/{len(dates)} dates scanned, {len(plan)} differ", flush=True)
            continue
        if stored_keys != fresh_keys or has_dupes:
            # A date in scope only because of duplicates keeps its own fire set -- deduplicating is
            # not a licence to re-derive a decision the CFTC fix did not touch. Those dates drop the
            # surplus rows in place instead of being deleted and re-inserted.
            rewrite = all_dates or moved
            dup_ids: list[int] = []
            if not rewrite:
                seen: set[tuple] = set()
                for r in stored:
                    k = _fire_key([r["var1_id"], r["var2_id"], r["var3_id"]], r["runic_combo"], r["status"])
                    if k in seen:
                        dup_ids.append(r["combo_id"])
                    else:
                        seen.add(k)
            plan.append({
                "rewrite": rewrite,
                "dup_ids": dup_ids,
                "date": date,
                "stored_ids": [r["combo_id"] for r in stored],
                "n_stored": len(stored),
                "n_stored_distinct": len(stored_keys),
                "n_fresh": len(fresh),
                "keys_differ": stored_keys != fresh_keys,
                "moved": moved,
                "added": sorted(fresh_keys - stored_keys),
                "removed": sorted(stored_keys - fresh_keys),
                "fresh": fresh,
                "pctile_move": moves_pair.get(date),
            })
        if i % 100 == 0:
            print(f"  {i}/{len(dates)} dates scanned, {len(plan)} differ", flush=True)

    rewritten = [p for p in plan if p["rewrite"]]
    dedupe_only = [p for p in plan if not p["rewrite"]]
    print(f"\nscope: {len(rewritten)} dates re-derived (CFTC percentile crossed a decision boundary), "
          f"{len(dedupe_only)} dates dedupe-only (history left as written)")
    keys_changed = [p for p in rewritten if p["keys_differ"]]
    dupes_only = [p for p in plan if not p["keys_differ"]]
    dup_rows = sum(p["n_stored"] - p["n_stored_distinct"] for p in plan)
    total_stored = sum(p["n_stored"] for p in plan)
    total_fresh = sum(p["n_fresh"] for p in plan)
    with_move = sum(1 for p in keys_changed if p["moved"])
    big_move = sum(
        1 for p in keys_changed
        if p["pctile_move"] and abs(p["pctile_move"][1] - p["pctile_move"][0]) > 10
    )

    print(f"\ndates touched: {len(plan)} of {len(dates)}")
    print(f"  with a genuinely different fire set: {len(keys_changed)}")
    print(f"  duplicate rows only (same fires inserted twice by repeated runs): {len(dupes_only)} dates")
    print(f"  exact duplicate rows removed across all touched dates: {dup_rows}")
    rw_stored = sum(p["n_stored"] for p in rewritten)
    rw_fresh = sum(p["n_fresh"] for p in rewritten)
    print(f"  on re-derived dates: {rw_stored} stored CFTC-leg rows -> {rw_fresh} re-derived")
    print(f"  across all touched dates: {total_stored} stored, {total_stored - dup_rows} distinct")
    if keys_changed:
        print(f"  attribution: {with_move} of {len(keys_changed)} changed dates "
              f"({100*with_move/len(keys_changed):.0f}%) crossed a CFTC decision boundary; "
              f"{big_move} moved by more than 10 percentile points. Re-derivation uses today's values "
              "for the other legs, so a change on a boundary-crossing date is CFTC-triggered but not "
              "necessarily CFTC-only.")
    added = sum(len(p["added"]) for p in keys_changed)
    removed = sum(len(p["removed"]) for p in keys_changed)
    print(f"  fire-set changes: {added} added, {removed} removed")
    by_combo: dict[str, int] = {}
    for p in keys_changed:
        for k in p["added"]:
            by_combo[f"+{k[1] or 'generic'}"] = by_combo.get(f"+{k[1] or 'generic'}", 0) + 1
        for k in p["removed"]:
            by_combo[f"-{k[1] or 'generic'}"] = by_combo.get(f"-{k[1] or 'generic'}", 0) + 1
    if by_combo:
        print("  by named combo: " + ", ".join(f"{k}={v}" for k, v in sorted(by_combo.items())))

    if not apply:
        print("\nDRY RUN - nothing written. Re-run with --apply.")
        return

    backup = db.with_suffix(f".pre_combo_replay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(db, backup)
    print(f"\nbackup written: {backup}")

    deleted = inserted = deduped = 0
    with conn:
        for p in plan:
            if not p["rewrite"]:
                if p["dup_ids"]:
                    marks = ",".join("?" * len(p["dup_ids"]))
                    conn.execute(f"DELETE FROM forward_returns WHERE combo_id IN ({marks})", p["dup_ids"])
                    conn.execute(f"DELETE FROM combo_fires WHERE combo_id IN ({marks})", p["dup_ids"])
                    deduped += len(p["dup_ids"])
                continue
            if p["stored_ids"]:
                marks = ",".join("?" * len(p["stored_ids"]))
                # forward_returns first: it is keyed on combo_id, so the rows must go with the fires
                # rather than be left pointing at ids that no longer exist.
                conn.execute(f"DELETE FROM forward_returns WHERE combo_id IN ({marks})", p["stored_ids"])
                conn.execute(f"DELETE FROM combo_fires WHERE combo_id IN ({marks})", p["stored_ids"])
                deleted += len(p["stored_ids"])
            for f in p["fresh"]:
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
                inserted += 1
    print(f"re-derived dates: deleted {deleted} CFTC-leg fires (and their forward_returns), inserted {inserted}")
    print(f"dedupe-only dates: removed {deduped} surplus duplicate rows in place")

    from src.macro_intelligence.engine.forward_returns import backfill_forward_returns

    filled = backfill_forward_returns()
    print(f"forward_returns refilled for {filled} fires")

    orphans = conn.execute(
        "SELECT COUNT(*) FROM forward_returns fr LEFT JOIN combo_fires cf ON fr.combo_id=cf.combo_id "
        "WHERE cf.combo_id IS NULL"
    ).fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM combo_fires cf LEFT JOIN forward_returns fr ON cf.combo_id=fr.combo_id "
        "WHERE fr.combo_id IS NULL"
    ).fetchone()[0]
    print(f"integrity: orphan forward_returns rows={orphans}, fires without returns={missing}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=ROOT / "macro_intelligence" / "data" / "runic.db")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit-dates", type=int, default=None, help="only the most recent N dates (testing)")
    ap.add_argument("--baseline", type=Path, default=None,
                    help="pre-restatement backup DB, used to decide which dates actually moved")
    ap.add_argument("--move-threshold", type=float, default=0.01,
                    help="ignore percentile changes smaller than this when testing boundary crossings")
    ap.add_argument("--all-dates", action="store_true",
                    help="re-derive every date, not just those whose CFTC percentile moved "
                         "(absorbs drift in every other series -- use deliberately)")
    args = ap.parse_args()
    replay(args.db, apply=args.apply, limit=args.limit_dates,
           move_threshold=args.move_threshold, all_dates=args.all_dates, baseline=args.baseline)


if __name__ == "__main__":
    main()
