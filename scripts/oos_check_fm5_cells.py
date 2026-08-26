#!/usr/bin/env python3
"""Out-of-sample checks on the FM<5 SQUEEZE cells before anyone acts on "100% on n=5".

The 2026-08-25 re-run left three cells above par: FM<5 with RM>40, >45 and >50, each showing
100% excess-hit on four or five episodes. Rohit's 4 Aug instruction was explicitly to prefer a
high hit rate on few episodes over a market-average result on many, so these cannot simply be
dismissed for small n. They have to be tested.

Four checks, none of which the grid itself can answer:

1. **Placebo** - draw random episode sets of the same size from the same calendar and ask how
   often all of them beat the market by chance. This is the question the bootstrap cannot answer,
   because the bootstrap resamples the cell's own episodes and so measures sampling variability
   around a result it assumes is real.
2. **Window sensitivity** - re-rank on 104 / 156 / 208 / 260-week windows. A real threshold effect
   should not depend on the window length used to define the threshold.
3. **Walk-forward** - split the sample in half. A cell that never fires in the first half has not
   been tested out of sample at all.
4. **Neighbour stability** - is FM<5 a plateau or a point? Rohit's own criticism of FM<10.

Writes ``cftc_oos_fm5_check`` as an artifact plus a markdown snippet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.cftc_pull import (  # noqa: E402
    fetch_cftc_asset_manager_net,
    fetch_cftc_fast_money_net,
)
from src.sentiment_superindex.analysis.cftc_episode_metrics import (  # noqa: E402
    analyze_cell,
    episode_return_table,
    load_analysis_context,
    weekly_pctile_series,
)
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet  # noqa: E402

HORIZON = "12w"
HORIZON_DAYS = {"12w": 60}


def _cell(ctx, fm_max, rm_min, *, index=None, fp=None, rp=None):
    fp = ctx["fm_pct"] if fp is None else fp
    rp = ctx["rm_pct"] if rp is None else rp
    ix = (index if index is not None else ctx["weekly_index"]).intersection(fp.index).intersection(rp.index)
    dates = ix[((fp.loc[ix] < fm_max) & (rp.loc[ix] > rm_min)).values]
    if len(dates) == 0:
        return None
    res = analyze_cell(
        pd.DatetimeIndex(dates), ctx["spx"], benchmark=ctx["benchmark"],
        sessions=ctx["sessions"], top_episodes=0,
    )
    m = res["metrics"][HORIZON]
    return {
        "n_episodes": res["n_episodes"],
        "mean": m.get("mean"),
        "mean_excess": m.get("mean_excess"),
        "hit_excess_pct": m.get("hit_excess_pct"),
    }


def placebo(ctx, sizes=(4, 5), draws: int = 400, seed: int = 11) -> list[dict]:
    rng = np.random.default_rng(seed)
    idx, spx, bench, sessions = ctx["weekly_index"], ctx["spx"], ctx["benchmark"], ctx["sessions"]
    out = []
    for size in sizes:
        wins = []
        for _ in range(draws):
            draw = pd.DatetimeIndex(sorted(rng.choice(idx, size=size, replace=False)))
            table = episode_return_table(spx, list(draw), HORIZON_DAYS, sessions=sessions, benchmark=bench)
            excess = [r[f"excess_{HORIZON}"] for r in table if r.get(f"excess_{HORIZON}") is not None]
            if len(excess) == size:
                wins.append(all(e > 0 for e in excess))
        p = float(np.mean(wins)) if wins else None
        out.append({
            "n_episodes": size,
            "draws": len(wins),
            "p_all_beat_market": round(p * 100, 1) if p else None,
            "one_in": round(1 / p) if p else None,
        })
    return out


def run(draws: int = 400) -> dict:
    ctx = load_analysis_context()
    fm, rm = fetch_cftc_fast_money_net(2006), fetch_cftc_asset_manager_net(2006)
    rm_levels = (40, 45, 50)

    windows = []
    for weeks in (104, 156, 208, 260):
        fp, rp = weekly_pctile_series(fm, weeks=weeks), weekly_pctile_series(rm, weeks=weeks)
        ix = fp.index.intersection(rp.index)
        windows.append({
            "weeks": weeks,
            "first_rank": str(fp.index.min().date()) if not fp.empty else None,
            "cells": {f"RM>{r}": _cell(ctx, 5, r, index=ix, fp=fp, rp=rp) for r in rm_levels},
        })

    idx = ctx["weekly_index"]
    mid = idx[len(idx) // 2]
    halves = {
        "split_at": str(mid.date()),
        "first_half": {f"RM>{r}": _cell(ctx, 5, r, index=idx[idx < mid]) for r in rm_levels},
        "second_half": {f"RM>{r}": _cell(ctx, 5, r, index=idx[idx >= mid]) for r in rm_levels},
    }
    neighbours = {f"FM<{v}": _cell(ctx, v, 45) for v in (2.5, 5, 6, 7.5, 10)}

    return {
        "test_id": "cftc_oos_fm5_check",
        "horizon": HORIZON,
        "par_excess_hit": (ctx.get("benchmark") or {}).get("note"),
        "placebo": placebo(ctx, draws=draws),
        "window_sensitivity": windows,
        "walk_forward": halves,
        "neighbours": neighbours,
    }


def report(payload: dict) -> str:
    lines = [
        "# FM<5 SQUEEZE cells — out-of-sample checks",
        "",
        "The re-run left FM<5 / RM>40, >45 and >50 above par at 100% excess-hit on four or five",
        "episodes. Small n alone is not a reason to dismiss them — the 4 Aug spec explicitly asked for",
        "high hit rates on few episodes over market-average results on many. These are the tests that",
        "decide it.",
        "",
        "## 1. Placebo — how often does a random set of the same size beat the market every time?",
        "",
        "| episodes | draws | P(all beat market) by chance | odds |",
        "|---------:|------:|-----------------------------:|------|",
    ]
    for row in payload["placebo"]:
        lines.append(
            f"| {row['n_episodes']} | {row['draws']} | {row['p_all_beat_market']}% | 1 in {row['one_in']} |"
        )
    lines += [
        "",
        "The bootstrap cannot answer this. It resamples the cell's own episodes, so it measures",
        "sampling variability around a result it already assumes is real. This asks the different and",
        "more important question: given 66 grid cells were searched, how surprising is the best one?",
        "",
        "## 2. Percentile-window sensitivity",
        "",
        "| window | first rank | RM>40 | RM>45 | RM>50 |",
        "|-------|-----------|-------|-------|-------|",
    ]

    def fmt(cell):
        if not cell:
            return "no fire"
        return f"n={cell['n_episodes']} ex={cell['mean_excess']}% hit={cell['hit_excess_pct']}%"

    for w in payload["window_sensitivity"]:
        lines.append(
            f"| {w['weeks']}w | {w['first_rank']} | " + " | ".join(fmt(w["cells"][f"RM>{r}"]) for r in (40, 45, 50)) + " |"
        )
    lines += [
        "",
        "## 3. Walk-forward halves",
        "",
        f"Split at **{payload['walk_forward']['split_at']}**.",
        "",
        "| cell | first half | second half |",
        "|------|-----------|-------------|",
    ]
    for r in (40, 45, 50):
        lines.append(
            f"| FM<5 RM>{r} | {fmt(payload['walk_forward']['first_half'][f'RM>{r}'])} | "
            f"{fmt(payload['walk_forward']['second_half'][f'RM>{r}'])} |"
        )
    lines += ["", "## 4. Neighbour stability (RM>45 held fixed)", "", "| FM cut | result |", "|--------|--------|"]
    for k, v in payload["neighbours"].items():
        lines.append(f"| {k} | {fmt(v)} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=400, help="placebo draws per episode count")
    args = ap.parse_args()
    payload = run(draws=args.draws)
    save_artifact("cftc_oos_fm5_check", payload)
    path = write_md_snippet("cftc_oos_fm5_check", report(payload))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
