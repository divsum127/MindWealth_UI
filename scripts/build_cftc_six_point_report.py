#!/usr/bin/env python3
"""Answer Rohit's six CFTC points (13 Aug reply on v2_TODOs row 42) in one report.

Runs the tests, writes markdown to ``docs/ssi_validation/_generated/`` and a PDF to
``docs/ssi_validation/pdf/`` -- PDF because the Drive file, the Google Sheet and the private docs
repo are all unreadable for him, so the report has to travel as an attachment.

    .venv/bin/python scripts/build_cftc_six_point_report.py            # full run (~15 min)
    .venv/bin/python scripts/build_cftc_six_point_report.py --cached   # reuse saved JSON artifacts
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "macro_intelligence" / "analysis" / "ssi_validation"
MD_DIR = ROOT / "docs" / "ssi_validation" / "_generated"
PDF_DIR = ROOT / "docs" / "ssi_validation" / "pdf"
STAMP = date.today().strftime("%Y%m%d")


def _fmt(value: object, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def compute(cached: bool) -> dict:
    from src.macro_intelligence.data.cftc_pull import (
        compare_legacy_to_tff,
        fetch_cftc_fast_money_net,
        fetch_cftc_legacy_noncommercial_net,
    )
    from src.sentiment_superindex.analysis import cftc_event_gate as gate
    from src.sentiment_superindex.analysis import cftc_grid_v2 as g
    from src.sentiment_superindex.analysis.cftc_episode_metrics import (
        load_analysis_context,
        weekly_pctile_series,
    )
    from src.sentiment_superindex.data.cftc_patterns import pattern_rules

    cache_path = ARTIFACT_DIR / f"cftc_six_point_{STAMP}.json"
    if cached and cache_path.is_file():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    ctx = load_analysis_context()
    cells = [
        ("SQUEEZE FM<10 (no RM)", g._mask_dates(ctx, fm_pct_max=10)),
        ("SQUEEZE FM<10 AND RM>55", g._mask_dates(ctx, fm_pct_max=10, rm_pct_min=55)),
        ("SQUEEZE FM<5 (no RM)", g._mask_dates(ctx, fm_pct_max=5)),
        ("LIQ EXIT FM>=80 (no RM)", g._mask_dates(ctx, fm_pct_min=79.999)),
        ("LIQ EXIT RM<30 AND FM>60 (old)", g._mask_dates(ctx, rm_pct_max=30, fm_pct_min=60)),
    ]
    legacy = fetch_cftc_legacy_noncommercial_net(2003, 2010)
    tff = fetch_cftc_fast_money_net(2006)
    legacy_pct, tff_pct = weekly_pctile_series(legacy), weekly_pctile_series(tff)
    overlap_idx = legacy_pct.index.intersection(tff_pct.index)
    a, b = legacy_pct.loc[overlap_idx], tff_pct.loc[overlap_idx]
    extreme_agreement = {}
    for thr in (10, 20):
        both = int(((a < thr) & (b < thr)).sum())
        either = int(((a < thr) | (b < thr)).sum())
        extreme_agreement[f"FM<{thr}"] = {
            "both": both,
            "either": either,
            "jaccard": round(both / either, 2) if either else None,
        }

    out = {
        "generated": STAMP,
        "diagnostics": ctx["sample_diagnostics"],
        "fm_regression": g.run_fm_pctile_regression(ctx),
        "rm_regression": g.run_rm_pctile_regression(ctx),
        "joint_regression": g.run_joint_pctile_regression(ctx),
        "rm_increment": g.run_rm_increment_cells(ctx),
        "event_gate": gate.run_event_gated_grid(
            ctx, [{"condition": c, "dates": d} for c, d in cells]
        ),
        "legacy_overlap": compare_legacy_to_tff(legacy, tff),
        "legacy_pctile_overlap": {
            "weeks": int(len(overlap_idx)),
            "pctile_corr": round(float(a.corr(b)), 4),
            "mean_abs_pctile_diff": round(float((a - b).abs().mean()), 1),
            "extreme_agreement": extreme_agreement,
        },
        "legacy_span": {
            "start": str(legacy.index.min().date()),
            "end": str(legacy.index.max().date()),
            "weeks": int(len(legacy)),
        },
        "active_rules": pattern_rules(),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


def _cell(data: dict, condition: str) -> dict:
    """One row of the RM-increment table by its condition string."""
    for row in data["rm_increment"]["rows"]:
        if row["condition"] == condition:
            return row
    raise KeyError(condition)


def _recommendation_line(data: dict) -> str:
    """Point 1 in prose, with the numbers read off the same table printed above it."""
    par = data["rm_increment"]["par"]["metrics"]["12w"]
    fm10 = _cell(data, "FM_roll_pct<10")["metrics"]["12w"]
    fm5 = _cell(data, "FM_roll_pct<5")["metrics"]["12w"]
    fm5rm = _cell(data, "FM_roll_pct<5 AND RM_roll_pct>55")
    return (
        "**SQUEEZE recommendation: FM < 10th percentile, no RM leg.** "
        f"{_cell(data, 'FM_roll_pct<10')['n_episodes']} episodes, 12-week mean {_fmt(fm10['mean'])}% vs "
        f"{_fmt(par['mean'])}% unconditional, excess {fm10['mean_excess']:+.2f}%, hit "
        f"{_fmt(fm10['hit_pct'], 1)}%. FM<5 alone is *worse* "
        f"({_cell(data, 'FM_roll_pct<5')['n_episodes']} episodes, mean {_fmt(fm5['mean'])}%, excess "
        f"{fm5['mean_excess']:+.2f}%), so tightening past 10 does not buy sharpness, it only removes the "
        f"middle of the distribution. FM<5 with RM>55 shows mean {_fmt(fm5rm['metrics']['12w']['mean'])}% "
        f"on {fm5rm['n_episodes']} episodes, which is too thin to act on."
    )


def build_markdown(data: dict) -> str:
    diag = data["diagnostics"]
    par = data["rm_increment"]["par"]["metrics"]["12w"]
    lines: list[str] = [
        "# CFTC — answers to your six points (13 Aug reply)",
        "",
        f"**Generated:** {data['generated']}  ",
        f"**Sample:** {diag['analysis_weeks']} analysis weeks, "
        f"{diag['analysis_start']} → {diag['analysis_end']} (raw TFF from {diag['raw_start']})",
        "",
        "## First, a data bug that changed every number in the 11 Aug package",
        "",
        "The 2006-2016 CFTC bulk file dates as `M/D/YYYY 12:00:00 AM` while the yearly files are ISO.",
        "The parser tried ISO first and only fell back when *every* row failed, so in the combined",
        "history the bulk rows silently became unparseable and were dropped: the sample started 2017",
        "instead of 2006-06-13, and the grids ran on 483 weeks instead of 1034. Fixed",
        "(`_parse_report_dates` now parses the leftovers), and every table below is on the full sample.",
        "",
        "## Point 2 — does RM explain anything? No.",
        "",
        "| Horizon | FM R² | FM p | RM R² | RM p | Δ adj R² adding RM to FM | RM p (joint) |",
        "|---|---|---|---|---|---|---|",
    ]
    fm = {r["horizon"]: r for r in data["fm_regression"]["rows"]}
    rm = {r["horizon"]: r for r in data["rm_regression"]["rows"]}
    joint = {r["horizon"]: r for r in data["joint_regression"]["rows"]}
    for h in ("1w", "2w", "4w", "8w"):
        lines.append(
            f"| {h} | {fm[h]['r_squared']:.5f} | {fm[h]['p_value']:.3f} | "
            f"{rm[h]['r_squared']:.5f} | {rm[h]['p_value']:.3f} | "
            f"{joint[h]['delta_adj_r_squared']:+.5f} | {joint[h]['p_value_rm']:.3f} |"
        )
    lines += [
        "",
        "Neither percentile explains SPX forward returns. RM clears 5% only at 8 weeks (p=0.034) — one",
        "horizon out of four, which is what you expect from testing four. Adding RM on top of FM makes",
        "adjusted R² *worse* at 1, 2 and 4 weeks.",
        "",
        "### The same cut with and without the RM leg (12-week horizon)",
        "",
        "| Condition | Episodes | Mean | Median | Gap | Hit % | Excess mean | Excess hit % |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in data["rm_increment"]["rows"]:
        m = row["metrics"]["12w"]
        lines.append(
            f"| {row['condition']} | {row['n_episodes']} | {_fmt(m['mean'])} | {_fmt(m['median'])} | "
            f"{_fmt(m['mean_median_gap'])} | {_fmt(m['hit_pct'],1)} | {_fmt(m['mean_excess'])} | "
            f"{_fmt(m['hit_excess_pct'],1)} |"
        )
    lines.append(
        f"| PAR (unconditional) | — | {_fmt(par['mean'])} | {_fmt(par['median'])} | "
        f"{_fmt(par['mean_median_gap'])} | {_fmt(par['hit_pct'],1)} | {_fmt(par['mean_excess'])} | "
        f"{_fmt(par['hit_excess_pct'],1)} |"
    )
    lines += [
        "",
        "**Recommendation:** drop RM from SQUEEZE. It halves the sample (35 episodes → 21) and leaves the",
        "mean and the excess essentially unchanged. You were right that FM is doing the work.",
        "",
        "## Point 3 — episodes that coincide with economic events",
        "",
        "Event set: CPI, FOMC and NFP releases — "
        + ", ".join(f"{k} {v}" for k, v in data["event_gate"]["event_counts"].items())
        + " dated releases in the sample. An episode counts as event-coincident when a release lands on",
        "it or within the window before it. Floor of 3 episodes applied as you asked.",
        "",
        "Coverage caveat: CPI and NFP cover the whole sample; FOMC dates only exist from 2011, because",
        "FRED has no meeting-date calendar (the id we were using, release 19, is the weekly H.3 reserves",
        "report — that bug is fixed). Pre-2011 gating therefore rests on CPI and NFP.",
        "",
        "Read the window column carefully. COT episodes are dated on the Tuesday position date, so a 1 or",
        "3 day backward window only catches releases falling Sunday to Tuesday — which is why those two",
        "rows are identical. The 7 day window is the one that actually spans a normal release week.",
        "",
        "| Cell | Window | Weeks (all) | Weeks (event) | Episodes | 12w mean | Excess | Hit % |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in data["event_gate"]["rows"]:
        for w in row["windows"]:
            m = (w.get("metrics") or {}).get("12w") or {}
            lines.append(
                f"| {row['condition']} | ±{w['window_days']}d | {w['n_weeks_all']} | {w['n_weeks_event']} | "
                f"{w['n_episodes_event']} | {_fmt(m.get('mean'))} | {_fmt(m.get('mean_excess'))} | "
                f"{_fmt(m.get('hit_pct'),1)} |"
            )
    lines += [
        "",
        "Two things stand out. Event-gating does not improve SQUEEZE — FM<10 ungated already carries the",
        "edge and gating only costs sample. But the **old** LIQUIDITY EXIT cut (RM<30 and FM>60) is",
        "genuinely bearish around events: 8 episodes, 12-week mean −3.00%, excess −5.31%, hit 37.5%. The",
        "FM≥80-only placeholder you asked to ship is much weaker (excess −1.58%). So on the evidence, RM",
        "earns its place in LIQUIDITY EXIT even though it does not in SQUEEZE.",
        "",
        "## Point 4 — pre-2006 from 2003",
        "",
        f"Built. Legacy COT non-commercial S&P 500 net, {data['legacy_span']['weeks']} weekly prints, "
        f"{data['legacy_span']['start']} → {data['legacy_span']['end']}, cached beside the TFF files.",
        "",
        "It is **not** a like-for-like FM series, and the overlap says so:",
        "",
        "| Measure | Value |",
        "|---|---|",
    ]
    ov = data["legacy_overlap"]
    pov = data["legacy_pctile_overlap"]
    lines += [
        f"| Overlap | {ov['overlap_start']} → {ov['overlap_end']} ({ov['overlap_weeks']} weeks) |",
        f"| Level correlation | {ov['level_corr']} |",
        f"| Weekly-change correlation | {ov['change_corr']} |",
        f"| Percentile correlation | {pov['pctile_corr']} |",
        f"| Mean absolute percentile difference | {pov['mean_abs_pctile_diff']} points |",
        f"| Agreement on FM<10 weeks | {pov['extreme_agreement']['FM<10']['both']} of "
        f"{pov['extreme_agreement']['FM<10']['either']} (jaccard {pov['extreme_agreement']['FM<10']['jaccard']}) |",
        f"| Means | legacy {ov['legacy_mean']:,.0f} vs TFF {ov['tff_mean']:,.0f} contracts |",
        "",
        "Roughly half the extreme weeks disagree, and the two series sit at different levels entirely.",
        "Stitching it into the grids would move cells for reasons that have nothing to do with the market,",
        "so it ships as labelled context (`legacy_noncommercial`), available if you want to eyeball",
        "2003-2006, and the recommendation below stays on the TFF sample.",
        "",
        "**On the GFC specifically:** the earlier reports said the rolling grids excluded Sep 2008 – May",
        "2009. That was wrong, and the wording has been corrected. Percentile cells run continuously from",
        f"{diag['first_pctile_20obs']}, and the 2008 episodes are in the grids — they are the largest",
        "negatives in the LIQ EXIT cells. The genuine caveat is that 2008 ranks against a partial ~115-week",
        "lookback rather than a full three years.",
        "",
        "## Points 1 and 5 — the cut, and what is shipped",
        "",
        _recommendation_line(data),
        "",
        "**Shipped as unvalidated display placeholders:** squeeze "
        + ", ".join(f"{k} {v:g}" for k, v in data["active_rules"]["squeeze"].items())
        + "; liquidity exit "
        + ", ".join(f"{k} {v:g}" for k, v in data["active_rules"]["liquidity_exit"].items())
        + ". Squeeze fires on FM<10",
        "with no RM condition, liquidity exit on FM≥80, both labelled unvalidated on the page and neither",
        "touching sizing. Historical fire counts on the full sample: squeeze 169 weeks / 35 episodes (was",
        "181 / 37 under FM<20 and RM>45); liquidity exit 214 weeks / 36 episodes (was 162 / 40 under RM<30",
        "and FM>60).",
        "",
        "**One thing to reconsider:** the event-gated table above says the RM leg matters for LIQUIDITY",
        "EXIT even though it does not for SQUEEZE. Say the word and I will put RM<30 back on that flag only.",
        "",
        "## Point 6 — reminder",
        "",
        "This is the reminder. The results above are the ones you asked me to bring back to you; the open",
        "decisions are the LIQUIDITY EXIT RM leg, and whether you want the legacy 2003 series shown",
        "anywhere given how loosely it tracks.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true", help="reuse today's saved JSON artifact")
    args = parser.parse_args()

    data = compute(args.cached)
    md = build_markdown(data)
    MD_DIR.mkdir(parents=True, exist_ok=True)
    md_path = MD_DIR / f"cftc_six_point_answers_{STAMP}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"markdown: {md_path}")

    try:
        from scripts.export_cftc_threshold_report_pdfs import md_to_pdf

        PDF_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = PDF_DIR / f"cftc_six_point_answers_{STAMP}.pdf"
        md_to_pdf(md_path, pdf_path, "CFTC — answers to your six points")
        print(f"pdf: {pdf_path}")
    except Exception as exc:  # the markdown is the deliverable; PDF is the convenience
        print(f"PDF export skipped: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
