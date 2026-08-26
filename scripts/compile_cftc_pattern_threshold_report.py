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
from src.sentiment_superindex.analysis.cftc_grid_v2 import (
    SQUEEZE_FM_THRESHOLDS,
    SQUEEZE_RM_THRESHOLDS,
    rank_cells_by_excess_hit,
)
from src.sentiment_superindex.analysis.cftc_report_format import (
    SIDE_CONVENTION_NOTE,
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
    diag = squeeze.get("sample_diagnostics") or {}
    lines.append(f"| Units | **{diag.get('unit_basis', 'emini_equivalent')}** — component contract lines at "
                 "notional weight; CFTC's 2023-05-02 redefinition of the Consolidated line is no longer a seam |")
    lines.append(f"| Raw weekly prints | {diag.get('raw_start', '—')} → {diag.get('raw_end', '—')} "
                 f"({diag.get('raw_weeks', '—')} weeks) |")
    lines.append(f"| Percentile window | {diag.get('pctile_window_weeks', 156)} weeks, rolling — "
                 "**partial windows are not ranked** |")
    lines.append(f"| Backtest start | **{diag.get('analysis_start', '—')}** (first full window; "
                 f"{diag.get('analysis_weeks', '—')} weeks) |")
    lines.append(f"| Unit-break scan | {diag.get('unit_breaks') or 'none'} |")
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

    par_hit = horizon_metrics(squeeze.get("par", {}), "12w").get("hit_excess_pct")
    ranked_hit = rank_cells_by_excess_hit(squeeze_rows, horizon="12w", par=squeeze.get("par"))
    rec = find_squeeze(squeeze_rows, 10, 55)
    splits = {s.get("condition"): s for s in (squeeze.get("seam_split") or [])}
    lines.append(
        f"**PAR (unconditional, {squeeze.get('par', {}).get('n_weeks', 0)} weeks): 12w excess-hit "
        f"{par_hit}%.** Every cell below is to be read against that number, not against its own win rate."
    )
    lines.append("")
    if rec:
        rm_ = horizon_metrics(rec, "12w")
        verdict = (
            "at par" if par_hit is not None and abs((rm_.get("hit_excess_pct") or 0) - par_hit) < 2
            else ("above par" if (rm_.get("hit_excess_pct") or 0) > (par_hit or 0) else "below par")
        )
        lines.append(
            f"1. **The previously recommended cell, `FM<10 / RM>55`, is {verdict}.** "
            f"n_ep={rec.get('n_episodes')}, mean={rm_.get('mean')}%, mean_excess={rm_.get('mean_excess')}%, "
            f"excess_hit={rm_.get('hit_excess_pct')}% against PAR {par_hit}%. It is not recommended."
        )
    if ranked_hit:
        top = ranked_hit[0]
        tm = horizon_metrics(top, "12w")
        split = splits.get(str(top.get("condition")), {})
        lines.append(
            f"2. **Highest excess-hit cell: `{top.get('condition')}`** — n_ep={top.get('n_episodes')}, "
            f"mean={tm.get('mean')}%, mean_excess={tm.get('mean_excess')}%, "
            f"excess_hit={tm.get('hit_excess_pct')}%. Pre/post 2023-05-02: "
            f"{(split.get('pre') or {}).get('n_episodes', 0)} vs "
            f"{(split.get('post') or {}).get('n_episodes', 0)} episodes, "
            f"survives={split.get('survives_split')}. **At that episode count this is an observation, "
            "not a threshold to sign** — two of its episodes are seven weeks apart in the same spring, "
            "and the most recent has no full 12w forward window yet."
        )
    legs = (liq.get("leg_availability") or {}).get("legs") or []
    rm_leg = next((l for l in legs if l.get("leg") == "RM_pct<30"), None)
    fm_leg = next((l for l in legs if l.get("leg") == "FM_pct>70"), None)
    if rm_leg and fm_leg:
        lines.append(
            f"3. **LIQUIDITY EXIT cannot fire, and it is the RM leg — not the FM units.** "
            f"`RM_pct<30` covered {rm_leg.get('pre_pct_of_weeks')}% of weeks before 2023-05-02 and "
            f"**{rm_leg.get('post_pct_of_weeks')}%** after; it last fired {rm_leg.get('last_fired')}, "
            f"{rm_leg.get('weeks_since_last_fired')} weeks ago. `FM_pct>70` still fires "
            f"({fm_leg.get('post_pct_of_weeks')}% of post-2023 weeks). Asset managers have been "
            "persistently net long since 2023, so a rolling rank of RM no longer reaches its floor. "
            "Restating the units does not bring the pattern back."
        )
    lines.append(
        "4. **FM percentile has no linear relationship with forward SPX returns** at any horizon "
        "(R² ≤ 0.003, p ≥ 0.10). A threshold effect would not show in a linear fit, so this does not "
        "close the question — but it does settle row 42: `invert=True` on `cot_fast_money` is "
        "immaterial either way."
    )
    lines.append("")
    lines.append("### Recommendation")
    lines.append("")
    lines.append(
        "**None — sign-off should stay held.** Nothing in this grid clears par by enough, on enough "
        "episodes, to be worth putting on the page. The two candidates are a 4–5 episode FM<5 cell and "
        "a LIQUIDITY EXIT pattern whose trigger leg has been unreachable for three years. Shipping a "
        "placeholder in the meantime would put a flag on the page that the data does not support."
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
    lines.append("| FM cut | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|--------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            m = horizon_metrics(row, "12w") if row else {}
            cells.append(str(m.get("mean_median_gap", "—")))
        lines.append(f"| FM<{fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### SQUEEZE heatmap — 12w excess_hit % (compare to PAR above)")
    lines.append("")
    lines.append("| FM cut | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|--------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            m = horizon_metrics(row, "12w") if row else {}
            hit = m.get("hit_excess_pct")
            cells.append(f"{hit} (n={row.get('n_episodes', 0)})" if hit is not None else "—")
        lines.append(f"| FM<{fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### SQUEEZE heatmap — 12w mean % (n_ep in parentheses)")
    lines.append("")
    lines.append("| FM cut | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|--------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            m = horizon_metrics(row, "12w") if row else {}
            n_ep = row.get("n_episodes", 0) if row else 0
            cells.append(f"{m.get('mean', '—')} (n={n_ep})" if m.get("mean") is not None else "—")
        lines.append(f"| FM<{fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### Episode count (n_ep / n_wk)")
    lines.append("")
    lines.append("| FM cut | " + " | ".join(f"RM>{r}" for r in rm_levels) + " |")
    lines.append("|--------|" + "|".join(["------"] * len(rm_levels)) + "|")
    for fm in fm_levels:
        cells = []
        for rm in rm_levels:
            row = find_squeeze(squeeze_rows, fm, rm)
            if row:
                cells.append(f"{row.get('n_episodes', 0)}/{row.get('n_weeks', 0)}")
            else:
                cells.append("0/0")
        lines.append(f"| FM<{fm} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. LIQUIDITY EXIT — top cells by 4w mean−median gap (RM ≤ 35, FM ≥ 45)")
    lines.append("")
    lines.append(SIDE_CONVENTION_NOTE)
    lines.append("")
    lines.append(distribution_table_header(fm_label="RM <", rm_label="FM >"))
    lines.append(distribution_table_sep())
    liq_top = rank_cells_by_gap(
        [r for r in liq_rows if r.get("rm_pct_max", 99) <= 35 and r.get("fm_pct_min", 0) >= 45],
        "4w",
        long_side=False,
    )[:15]
    for r in liq_top:
        lines.append(distribution_table_line(r, "4w", fm_key="rm_pct_max", rm_key="fm_pct_min"))
    lines.append("")
    lines.append("### Dated instances for the cells above (most favourable first for a short)")
    lines.append("")
    for r in liq_top:
        lines.append(f"- `{r.get('condition')}`: {format_episode_instances(r, '4w', long_side=False)}")
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
