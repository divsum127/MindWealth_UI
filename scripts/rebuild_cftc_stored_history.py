#!/usr/bin/env python3
"""Rebuild stored CFTC history after the 2023-05-02 unit restatement.

Fixing the pull does not repair what is already on disk. ``daily_readings.CFTC`` and
``cftc_positioning`` were written week by week as the data arrived, so every row before
2023-05-02 is in the old unit (big-contract equivalents, micro excluded) and every row after it
is in the new one. The stored series is therefore mixed-unit end to end, and every stored
``pctile_rank_3yr`` whose 156-week window spans that date was ranked across the change.

Measured on the live DB before this script existed:

* pre-2023 rows: 0 of 672 match the restated series (median -57,059 against -284,526)
* stored percentiles: mean absolute error 5.2 points, 20% of days off by more than 10 points,
  5.3% off by more than 25
* Combo E's ``CFTC >= 85th`` leg: 22 days flip (16 false passes, 6 missed fires)

Default is a dry run that prints the diff and writes nothing.

    python scripts/rebuild_cftc_stored_history.py --db macro_intelligence/data/runic.db
    python scripts/rebuild_cftc_stored_history.py --db ... --apply
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.cftc_pull import (  # noqa: E402
    detect_unit_break,
    fetch_cftc_asset_manager_net,
    fetch_cftc_fast_money_net,
)
from src.macro_intelligence.engine.percentiles import percentile_rank  # noqa: E402

SEAM = pd.Timestamp("2023-05-02")


def _rolling_pctile(series: pd.Series, weeks: int) -> pd.Series:
    """Rank each week against a *full* trailing window; blank until the window closes."""
    out: dict[pd.Timestamp, float | None] = {}
    for i, ts in enumerate(series.index):
        window = series.iloc[: i + 1]
        window = window[window.index >= ts - pd.DateOffset(weeks=weeks)]
        out[ts] = percentile_rank(float(series.iloc[i]), window) if len(window) >= weeks else None
    return pd.Series(out)


def build_reference() -> pd.DataFrame:
    weeks = int(load_config().get("cftc", {}).get("pctile_window_weeks", 156))
    fm = fetch_cftc_fast_money_net(2006)
    rm = fetch_cftc_asset_manager_net(2006)
    if fm.empty:
        raise SystemExit("no CFTC data - check macro_intelligence/data_cache/cftc")
    breaks = detect_unit_break(pd.DataFrame({"fm_net": fm, "rm_net": rm}).dropna(how="all"))
    if breaks:
        raise SystemExit(f"refusing to rebuild: the source series itself has a unit break: {breaks}")
    return pd.DataFrame(
        {"fm": fm, "rm": rm, "fm_p": _rolling_pctile(fm, weeks), "rm_p": _rolling_pctile(rm, weeks)}
    ).sort_index()


def _asof(stored_dates: pd.Series, ref: pd.DataFrame) -> pd.DataFrame:
    """Attach the weekly print in effect on each stored (daily) date."""
    left = pd.DataFrame({"date": pd.to_datetime(stored_dates)}).sort_values("date")
    right = ref.reset_index().rename(columns={"index": "wk"}).sort_values("wk")
    return pd.merge_asof(left, right, left_on="date", right_on="wk")


def rebuild(db: Path, *, apply: bool) -> None:
    ref = build_reference()
    conn = sqlite3.connect(db)

    readings = pd.read_sql(
        "SELECT date, raw_value, pctile_rank_3yr FROM daily_readings WHERE var_id='CFTC' ORDER BY date",
        conn,
    )
    merged = _asof(readings["date"], ref)
    merged["old_raw"] = readings.sort_values("date")["raw_value"].values
    merged["old_pct"] = readings.sort_values("date")["pctile_rank_3yr"].values

    changed_raw = int((merged["fm"] - merged["old_raw"]).abs().gt(1).sum())
    comparable = merged.dropna(subset=["fm_p", "old_pct"])
    changed_pct = int((comparable["fm_p"] - comparable["old_pct"]).abs().gt(0.01).sum())
    pre = merged[merged["date"] < SEAM]
    print(f"daily_readings.CFTC: {len(merged)} rows | raw changing: {changed_raw} | pctile changing: {changed_pct}")
    print(f"  pre-seam rows (all in the old unit): {len(pre)}")
    print(f"  median raw pre-seam: stored {pre['old_raw'].median():,.0f} -> restated {pre['fm'].median():,.0f}")

    positioning = pd.read_sql("SELECT date, fm_net, rm_net, fm_pctile, rm_pctile FROM cftc_positioning ORDER BY date", conn)
    pos_merged = _asof(positioning["date"], ref)
    pos_changed = int((pos_merged["fm"] - positioning.sort_values("date")["fm_net"].values).__abs__().gt(1).sum())
    print(f"cftc_positioning: {len(positioning)} rows | fm_net changing: {pos_changed}")

    if not apply:
        print("\nDRY RUN - nothing written. Re-run with --apply to rebuild.")
        return

    backup = db.with_suffix(f".pre_cftc_restate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(db, backup)
    print(f"\nbackup written: {backup}")

    with conn:
        for _, row in merged.iterrows():
            if pd.isna(row["fm"]):
                continue
            conn.execute(
                "UPDATE daily_readings SET raw_value=?, pctile_rank_3yr=? WHERE var_id='CFTC' AND date=?",
                (
                    float(row["fm"]),
                    None if pd.isna(row["fm_p"]) else float(row["fm_p"]),
                    row["date"].strftime("%Y-%m-%d"),
                ),
            )
        for _, row in pos_merged.iterrows():
            if pd.isna(row["fm"]):
                continue
            conn.execute(
                "UPDATE cftc_positioning SET fm_net=?, rm_net=?, fm_pctile=?, rm_pctile=? WHERE date=?",
                (
                    float(row["fm"]),
                    None if pd.isna(row["rm"]) else float(row["rm"]),
                    None if pd.isna(row["fm_p"]) else float(row["fm_p"]),
                    None if pd.isna(row["rm_p"]) else float(row["rm_p"]),
                    row["date"].strftime("%Y-%m-%d"),
                ),
            )
    print("rebuild applied.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=ROOT / "macro_intelligence" / "data" / "runic.db")
    ap.add_argument("--apply", action="store_true", help="write the rebuild (a timestamped backup is taken first)")
    args = ap.parse_args()
    rebuild(args.db, apply=args.apply)


if __name__ == "__main__":
    main()
