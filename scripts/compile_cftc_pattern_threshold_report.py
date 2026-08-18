#!/usr/bin/env python3
"""Compile CFTC SQUEEZE / LIQUIDITY EXIT threshold report for Rohit sign-off."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.cftc_pull import (
    fetch_cftc_asset_manager_net,
    fetch_cftc_fast_money_net,
)
from src.sentiment_superindex.analysis.cftc_grid_v2 import SQUEEZE_FM_THRESHOLDS, SQUEEZE_RM_THRESHOLDS
from src.sentiment_superindex.analysis.cftc_report_format import (
    distribution_table_header,
    distribution_table_line,
    distribution_table_sep,
    format_cell_line,
    format_episode_instances,
    format_heatmap_cell,
    format_par_section,
    horizon_metrics,
    rank_cells_by_gap,
    worked_examples_section,
)

ART = ROOT / "macro_intelligence" / "analysis" / "ssi_validation"


def latest(pattern: str) -> Path:
    files = sorted(ART.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No artifacts matching {pattern}")
    return files[-1]


def find_squeeze(rows: list[dict], fm_max: float, rm_min: int) -> dict | None:
    for r in rows:
        if r.get("fm_pct_max") == fm_max and r.get("rm_pct_min") == rm_min and r.get("pattern") == "SQUEEZE":
            return r
        if r.get("fm_max") == fm_max and r.get("rm_min") == rm_min:
            return r
    return None


def find_liq(rows: list[dict], rm_max: int, fm_min: int) -> dict | None:
    for r in rows:
        if r.get("rm_pct_max") == rm_max and r.get("fm_pct_min") == fm_min:
            return r
        if r.get("rm_max") == rm_max and r.get("fm_min") == fm_min:
            return r
    return None


def compile_report(*, squeeze_path: Path, liq_path: Path, out_path: Path) -> None:
    squeeze = json.loads(squeeze_path.read_text(encoding="utf-8"))
    liq = json.loads(liq_path.read_text(encoding="utf-8"))
    squeeze_rows = [r for r in squeeze["rows"] if r.get("pattern", "SQUEEZE") == "SQUEEZE"]
    liq_rows = liq["rows"]

    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()

    ranked_12w = rank_cells_by_gap(squeeze_rows, "12w", squeeze_only=True)
    best_squeeze = ranked_12w[0] if ranked_12w else None
    pdf_squeeze = find_squeeze(squeeze_rows, 30, 50)
    pdf_liq = find_liq(liq_rows, 30, 60)

    fm_levels = list(SQUEEZE_FM_THRESHOLDS)
    rm_levels = list(SQUEEZE_RM_THRESHOLDS)

    lines: list[str] = []
    lines.append("# CFTC Positioning Pattern Thresholds — Experiment Results for Sign-Off")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Purpose")
    lines.append("")
    lines.append(
        "Grid-search results for **SQUEEZE** (FM low + RM high) and **LIQUIDITY EXIT** "
        "(RM low + FM high) before locking production Sentiment Layer 3 flags. "
        "**Display/alert only** — not SSI sizing gates (per 2 Aug email)."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Data & methodology")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|------|-------|")
    lines.append(f"| CFTC Fast Money through | **{fm.index[-1].strftime('%Y-%m-%d')}** (Tuesday position date) |")
    lines.append(f"| CFTC Real Money through | **{rm.index[-1].strftime('%Y-%m-%d')}** |")
    lines.append("| Percentile window | 156 weeks (~3 years), rolling |")
    lines.append("| Backtest start | 2006-01-01 |")
    lines.append("| Episode collapse | Consecutive qualifying weeks → one episode (first fire date) |")
    lines.append("| Forward returns | S&P 500 at 4w / 8w / 12w trading days |")
    lines.append("| Benchmark | Mean SPX return across **all** weeks in sample per horizon |")
    lines.append("| Excess | Per-episode SPX return minus benchmark; excess_hit = beat market |")
    lines.append("| **Ranking metric** | **Mean − median gap** (tail marker), not Sharpe |")
    lines.append("| Per-cell columns | n_wk, n_ep, mean, median, gap, hit %, best, worst, top dated instances |")
    lines.append(f"| SQUEEZE JSON | `{squeeze_path.name}` |")
    lines.append(f"| LIQUIDITY EXIT JSON | `{liq_path.name}` |")
    lines.append("")
    lines.append("**SQUEEZE:** FM pctile < X AND RM pctile > Y (same week).")
    lines.append("")
    lines.append("**LIQUIDITY EXIT:** RM pctile < X AND FM pctile > Y.")
    lines.append("")
    lines.append(worked_examples_section())
    lines += format_par_section(
        squeeze.get("par", {}),
        benchmark=squeeze.get("benchmark"),
        horizons=["4w", "8w", "12w"],
    )
    lines.append("---")
    lines.append("")
    lines.append("## 3. Executive summary")
    lines.append("")

    if best_squeeze:
        m = horizon_metrics(best_squeeze, "12w")
        lines.append(
            f"1. **SQUEEZE** top cell by 12w mean−median gap: "
            f"**`{best_squeeze.get('condition')}`** "
            f"(n_ep={best_squeeze.get('n_episodes')}, n_wk={best_squeeze.get('n_weeks')}, "
            f"gap={m.get('mean_median_gap')}%, mean={m.get('mean')}%, hit={m.get('hit_pct')}%, "
            f"excess_hit={m.get('hit_excess_pct')}%). "
            f"Prior Sharpe-ranked FM<20/RM>45 shows **negative** gap — tracks market, not tail."
        )
    else:
        lines.append("1. **SQUEEZE** — no rolling cells with computable 12w mean−median gap.")
    if pdf_squeeze:
        ps = horizon_metrics(pdf_squeeze, "12w")
        lines.append(
            f"2. PDF default FM<30/RM>50: n_ep={pdf_squeeze.get('n_episodes')}, "
            f"gap={ps.get('mean_median_gap')}%, mean={ps.get('mean')}%, hit={ps.get('hit_pct')}%."
        )
    if pdf_liq:
        p4 = horizon_metrics(pdf_liq, "4w")
        p12 = horizon_metrics(pdf_liq, "12w")
        lines.append(
            f"3. **LIQUIDITY EXIT** RM<30/FM>60: n_ep={pdf_liq.get('n_episodes')}, "
            f"4w gap={p4.get('mean_median_gap')}%, hit={p4.get('hit_pct')}%, "
            f"12w mean={p12.get('mean')}% — modest stress flag, not a strong short."
        )
    lines.append("4. Patterns are **common** (~5–10 fires/year) — use as context flags only.")
    lines.append("")
    lines.append("### Recommended options")
    lines.append("")
    lines.append("| Pattern | Option A (tail gap) | Option B (PDF / more frequent) |")
    lines.append("|---------|---------------------|-------------------------------|")
    if best_squeeze:
        bm = horizon_metrics(best_squeeze, "12w")
        lines.append(
            f"| SQUEEZE | see §4 top gap cells (e.g. `{best_squeeze.get('condition')}`, gap {bm.get('mean_median_gap')}%) | "
            f"FM **< 30**, RM **> 50** (gap {horizon_metrics(pdf_squeeze, '12w').get('mean_median_gap') if pdf_squeeze else '—'}) |"
        )
    if pdf_liq:
        lines.append(
            f"| LIQUIDITY EXIT | RM **< 25**, FM **> 55** (see §5) | "
            f"RM **< 30**, FM **> 60** (n_ep={pdf_liq.get('n_episodes')}, 4w hit {horizon_metrics(pdf_liq, '4w').get('hit_pct')}%) |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. SQUEEZE — full distribution per cell (12w, ranked by mean−median gap)")
    lines.append("")
    lines.append(distribution_table_header(include_instances=True))
    lines.append(distribution_table_sep(include_instances=True))
    for row in ranked_12w:
        lines.append(distribution_table_line(row, "12w", include_instances=True))
    lines.append("")
    lines.append("### SQUEEZE heatmap — 12w mean−median gap")
    lines.append("")
    lines.append("| FM < | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            m = horizon_metrics(row, "12w") if row else {}
            cells.append(str(m.get("mean_median_gap", "—")))
        lines.append(f"| {fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### SQUEEZE heatmap — 12w excess_hit % (compare to PAR above)")
    lines.append("")
    lines.append("| FM < | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            cells.append(format_heatmap_cell(row, "12w"))
        lines.append(f"| {fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### SQUEEZE heatmap — 12w mean % (n_ep in parentheses)")
    lines.append("")
    lines.append("| FM < | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            m = horizon_metrics(row, "12w") if row else {}
            n_ep = row.get("n_episodes", 0) if row else 0
            cells.append(f"{m.get('mean', '—')} (n={n_ep})" if m.get("mean") is not None else "—")
        lines.append(f"| {fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### Episode count (n_ep / n_wk)")
    lines.append("")
    lines.append("| FM < | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            if row:
                cells.append(f"{row.get('n_episodes', 0)}/{row.get('n_weeks', 0)}")
            else:
                cells.append("0/0")
        lines.append(f"| {fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. LIQUIDITY EXIT — top cells by 4w mean−median gap (RM ≤ 35, FM ≥ 45)")
    lines.append("")
    lines.append("| RM < | FM > | n_wk | n_ep | mean % | median % | gap % | hit % | best % | worst % | top instances |")
    lines.append("|------|------|------|------|--------|----------|-------|-------|--------|---------|-----------------|")
    liq_top = rank_cells_by_gap(
        [r for r in liq_rows if r.get("rm_pct_max", 99) <= 35 and r.get("fm_pct_min", 0) >= 45],
        "4w",
        long_side=False,
    )[:15]
    for r in liq_top:
        m = horizon_metrics(r, "4w")
        lines.append(
            f"| {r.get('rm_pct_max')} | {r.get('fm_pct_min')} | {r.get('n_weeks')} | {r.get('n_episodes')} | "
            f"{m.get('mean')} | {m.get('median')} | {m.get('mean_median_gap')} | {m.get('hit_pct')} | "
            f"{m.get('best')} | {m.get('worst')} | {format_episode_instances(r, '4w')} |"
        )
    lines.append("")
    if pdf_liq:
        lines.append("### PDF default RM<30, FM>60")
        lines.append("")
        for label in ("4w", "8w", "12w"):
            m = horizon_metrics(pdf_liq, label)
            lines.append(
                f"- **{label}:** n_ep={pdf_liq.get('n_episodes')}, mean={m.get('mean')}%, "
                f"median={m.get('median')}%, gap={m.get('mean_median_gap')}%, "
                f"hit={m.get('hit_pct')}%, best={m.get('best')}%, worst={m.get('worst')}%"
            )
        lines.append(f"- top 4w: {format_episode_instances(pdf_liq, '4w')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Sign-off")
    lines.append("")
    lines.append("**SQUEEZE:** FM < ___ , RM > ___  (rank by mean−median gap + dated instances)")
    lines.append("")
    lines.append("**LIQUIDITY EXIT:** RM < ___ , FM > ___")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("cd MindWealth_UI")
    lines.append(".venv/bin/python scripts/run_cftc_rohit_rerun.py")
    lines.append(".venv/bin/python scripts/compile_cftc_pattern_threshold_report.py")
    lines.append("```")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--squeeze", type=Path, default=None)
    parser.add_argument("--liquidity", type=Path, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "docs" / "ssi_validation" / f"CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_{datetime.now().strftime('%Y%m%d')}.md",
    )
    args = parser.parse_args()
    squeeze_path = args.squeeze or latest("03_squeeze_grid_*.json")
    liq_path = args.liquidity or latest("04_liquidity_exit_grid_*.json")
    compile_report(squeeze_path=squeeze_path, liq_path=liq_path, out_path=args.out)
    print(f"Wrote {args.out}")
    print(f"Using {squeeze_path.name}, {liq_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
