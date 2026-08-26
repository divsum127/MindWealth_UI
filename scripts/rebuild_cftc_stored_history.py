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

Four percentile columns carry the contamination, not one. ``pctile_rank_3yr`` is what the SSI panel
shows, but combo detection reads ``unconditional_pctile`` (see ``combo_pctile_from_reading``), and
``emission_vectors`` keeps its own copy of both. All of them are rebuilt here.

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
from src.macro_intelligence.engine.percentiles import (  # noqa: E402
    compute_unconditional_pctile,
    percentile_rank,
)

SEAM = pd.Timestamp("2023-05-02")


def _rolling_pctile(series: pd.Series, weeks: int) -> pd.Series:
    """Rank each week against a *full* trailing window; blank until the window closes."""
    out: dict[pd.Timestamp, float | None] = {}
    for i, ts in enumerate(series.index):
        window = series.iloc[: i + 1]
        window = window[window.index >= ts - pd.DateOffset(weeks=weeks)]
        out[ts] = percentile_rank(float(series.iloc[i]), window) if len(window) >= weeks else None
    return pd.Series(out)


def _unconditional_series(fm: pd.Series, var_cfg: dict) -> pd.Series:
    """``unconditional_pctile`` as the engine computes it: rolling 3 calendar years, no full-window rule.

    This is the column combo detection actually reads, so it has to be reproduced the engine's way
    rather than approximated with the 156-week rank.
    """
    return pd.Series(
        {ts: compute_unconditional_pctile(fm, var_cfg, ts) for ts in fm.index}, dtype=float
    )


def build_reference() -> pd.DataFrame:
    weeks = int(load_config().get("cftc", {}).get("pctile_window_weeks", 156))
    fm = fetch_cftc_fast_money_net(2006)
    rm = fetch_cftc_asset_manager_net(2006)
    if fm.empty:
        raise SystemExit("no CFTC data - check macro_intelligence/data_cache/cftc")
    breaks = detect_unit_break(pd.DataFrame({"fm_net": fm, "rm_net": rm}).dropna(how="all"))
    if breaks:
        raise SystemExit(f"refusing to rebuild: the source series itself has a unit break: {breaks}")
    var_cfg = {"pctile_window": "rolling_3y", "pctile_start": "2006-01-01"}
    return pd.DataFrame(
        {
            "fm": fm,
            "rm": rm,
            "fm_p": _rolling_pctile(fm, weeks),
            "rm_p": _rolling_pctile(rm, weeks),
            "fm_uncond": _unconditional_series(fm, var_cfg),
        }
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
        "SELECT date, raw_value, pctile_rank_3yr, unconditional_pctile FROM daily_readings "
        "WHERE var_id='CFTC' ORDER BY date",
        conn,
    )
    merged = _asof(readings["date"], ref)
    merged["old_raw"] = readings.sort_values("date")["raw_value"].values
    merged["old_pct"] = readings.sort_values("date")["pctile_rank_3yr"].values
    merged["old_uncond"] = readings.sort_values("date")["unconditional_pctile"].values

    changed_raw = int((merged["fm"] - merged["old_raw"]).abs().gt(1).sum())
    comparable = merged.dropna(subset=["fm_p", "old_pct"])
    changed_pct = int((comparable["fm_p"] - comparable["old_pct"]).abs().gt(0.01).sum())
    pre = merged[merged["date"] < SEAM]
    print(f"daily_readings.CFTC: {len(merged)} rows | raw changing: {changed_raw} | pctile changing: {changed_pct}")
    print(f"  pre-seam rows (all in the old unit): {len(pre)}")
    print(f"  median raw pre-seam: stored {pre['old_raw'].median():,.0f} -> restated {pre['fm'].median():,.0f}")

    # unconditional_pctile is the column combo detection reads, so its error is the one that moves
    # gate decisions. Reported separately from the panel percentile.
    comp_u = merged.dropna(subset=["fm_uncond", "old_uncond"])
    if len(comp_u):
        err = (comp_u["fm_uncond"] - comp_u["old_uncond"]).abs()
        print(f"  unconditional_pctile: changing {int(err.gt(0.01).sum())} rows | mean |error| {err.mean():.1f} pts")
        old_leg, new_leg = comp_u["old_uncond"] >= 85, comp_u["fm_uncond"] >= 85
        print(f"  Combo E 'CFTC >= 85th' leg: {int((old_leg != new_leg).sum())} days flip "
              f"({int((old_leg & ~new_leg).sum())} false passes, {int((~old_leg & new_leg).sum())} missed)")

    emissions = pd.read_sql(
        "SELECT date, unconditional_pctile FROM emission_vectors WHERE var_id='CFTC' ORDER BY date", conn
    )
    em_merged = _asof(emissions["date"], ref)
    em_merged["old_uncond"] = emissions.sort_values("date")["unconditional_pctile"].values
    em_cmp = em_merged.dropna(subset=["fm_uncond", "old_uncond"])
    print(f"emission_vectors.CFTC: {len(emissions)} rows | "
          f"unconditional_pctile changing: {int((em_cmp['fm_uncond'] - em_cmp['old_uncond']).abs().gt(0.01).sum())}")

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
            uncond = None if pd.isna(row["fm_uncond"]) else float(row["fm_uncond"])
            conn.execute(
                "UPDATE daily_readings SET raw_value=?, pctile_rank_3yr=?, unconditional_pctile=?, "
                "regime_pctile=? WHERE var_id='CFTC' AND date=?",
                (
                    float(row["fm"]),
                    None if pd.isna(row["fm_p"]) else float(row["fm_p"]),
                    uncond,
                    # regime_pctile falls back to the unconditional figure whenever the fed-cycle
                    # sample is too thin, which is how every stored CFTC row was written (they match
                    # column for column). Rebuilding it as the unconditional value preserves that.
                    uncond,
                    row["date"].strftime("%Y-%m-%d"),
                ),
            )
        for _, row in em_merged.iterrows():
            if pd.isna(row["fm_uncond"]):
                continue
            conn.execute(
                "UPDATE emission_vectors SET unconditional_pctile=?, regime_pctile=? "
                "WHERE var_id='CFTC' AND date=?",
                (float(row["fm_uncond"]), float(row["fm_uncond"]), row["date"].strftime("%Y-%m-%d")),
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
