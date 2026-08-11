"""CFTC SQUEEZE / LIQUIDITY EXIT re-run per Rohit Aug 2026 spec."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.analysis.cftc_episode_metrics import (
    DEFAULT_HORIZONS,
    analyze_cell,
    analyze_par_row,
    load_analysis_context,
    stationary_block_bootstrap,
    subsample_stability_weekly,
)
from src.sentiment_superindex.analysis.cftc_report_format import (
    distribution_table_header,
    distribution_table_line,
    distribution_table_sep,
    format_cell_line,
    format_episode_instances,
    format_heatmap_cell,
    format_par_section,
    rank_cells_by_gap,
    worked_examples_section,
)
from src.sentiment_superindex.analysis.report_utils import GENERATED_DOCS, save_artifact, stamp, write_md_snippet

SQUEEZE_FM_THRESHOLDS = [5, 7.5, 10, 12.5, 15, 20, 25, 30, 35, 40, 45]
SQUEEZE_RM_THRESHOLDS = list(range(40, 70, 5))
LIQ_RM_THRESHOLDS = list(range(15, 45, 5))
LIQ_FM_THRESHOLDS = list(range(45, 80, 5))

# Primary robustness targets (Rohit: FM<7.5 subsample stability)
ROBUSTNESS_KEY_CELLS: list[dict[str, Any]] = [
    {
        "condition": "FM_roll_pct<7.5 AND RM_roll_pct>45",
        "fm_pct_max": 7.5,
        "rm_pct_min": 45,
        "long_side": True,
    },
    {
        "condition": "FM_roll_pct<7.5 AND RM_roll_pct>40",
        "fm_pct_max": 7.5,
        "rm_pct_min": 40,
        "long_side": True,
    },
    {
        "condition": "FM_roll_pct<7.5 AND FM_net<0",
        "fm_pct_max": 7.5,
        "fm_net_max": 0.0,
        "long_side": True,
    },
    {
        "condition": "FM_roll_pct<5 AND RM_roll_pct>45",
        "fm_pct_max": 5.0,
        "rm_pct_min": 45,
        "long_side": True,
    },
]


def _mask_dates(
    ctx: dict[str, Any],
    *,
    fm_pct_max: float | None = None,
    rm_pct_min: float | None = None,
    rm_pct_max: float | None = None,
    fm_pct_min: float | None = None,
    fm_net_max: float | None = None,
    fm_net_fixed_pctile: float | None = None,
) -> pd.DatetimeIndex:
    idx = ctx["weekly_index"]
    fm = ctx["fm"]
    fm_pct = ctx["fm_pct"]
    rm_pct = ctx["rm_pct"]
    mask = pd.Series(True, index=idx)
    if fm_pct_max is not None:
        mask &= fm_pct.loc[idx] < fm_pct_max
    if rm_pct_min is not None:
        mask &= rm_pct.loc[idx] > rm_pct_min
    if rm_pct_max is not None:
        mask &= rm_pct.loc[idx] < rm_pct_max
    if fm_pct_min is not None:
        mask &= fm_pct.loc[idx] > fm_pct_min
    if fm_net_max is not None:
        mask &= fm.loc[idx] < fm_net_max
    if fm_net_fixed_pctile is not None:
        cuts = ctx["fm_distribution"]
        key = {2.5: "p2_5", 5.0: "p5", 10.0: "p10"}.get(fm_net_fixed_pctile)
        if key and cuts.get(key) is not None:
            mask &= fm.loc[idx] < cuts[key]
    return idx[mask.fillna(False)]


def run_par_row(ctx: dict[str, Any]) -> dict[str, Any]:
    return analyze_par_row(
        ctx["weekly_index"],
        ctx["spx"],
        benchmark=ctx["benchmark"],
        sessions=ctx["sessions"],
    )


def run_squeeze_grid_v2(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = ctx or load_analysis_context()
    rows: list[dict[str, Any]] = []
    for fm_thr in SQUEEZE_FM_THRESHOLDS:
        for rm_thr in SQUEEZE_RM_THRESHOLDS:
            dates = _mask_dates(ctx, fm_pct_max=fm_thr, rm_pct_min=rm_thr)
            cell = analyze_cell(
                dates,
                ctx["spx"],
                benchmark=ctx["benchmark"],
                long_side=True,
            )
            rows.append(
                {
                    "pattern": "SQUEEZE",
                    "condition": f"FM_roll_pct<{fm_thr} AND RM_roll_pct>{rm_thr}",
                    "fm_pct_max": fm_thr,
                    "rm_pct_min": rm_thr,
                    **cell,
                }
            )
    # Absolute-level AND cuts (Rohit §4): FM rolling pct + net<0, and fixed distribution cuts
    for fm_thr in [10, 7.5, 5]:
        dates = _mask_dates(ctx, fm_pct_max=fm_thr, fm_net_max=0.0)
        if len(dates) == 0:
            continue
        cell = analyze_cell(dates, ctx["spx"], benchmark=ctx["benchmark"], long_side=True)
        rows.append(
            {
                "pattern": "SQUEEZE_ABS",
                "condition": f"FM_roll_pct<{fm_thr} AND FM_net<0",
                "fm_pct_max": fm_thr,
                "fm_net_max": 0,
                **cell,
            }
        )
    for pct_label, pct_val in [("p2.5", 2.5), ("p5", 5.0), ("p10", 10.0)]:
        dates = _mask_dates(ctx, fm_net_fixed_pctile=pct_val)
        if len(dates) == 0:
            continue
        cell = analyze_cell(dates, ctx["spx"], benchmark=ctx["benchmark"], long_side=True)
        rows.append(
            {
                "pattern": "SQUEEZE_ABS",
                "condition": f"FM_net<fixed_{pct_label}",
                "fm_net_fixed_pctile": pct_val,
                **cell,
            }
        )
    return {
        "test_id": "03_squeeze_grid_v2",
        "spec": "rohit_2026-08-04",
        "data_note": ctx["data_note"],
        "sample_diagnostics": ctx.get("sample_diagnostics"),
        "fm_distribution": ctx["fm_distribution"],
        "benchmark": ctx["benchmark"],
        "par": run_par_row(ctx),
        "rows": rows,
    }


def run_liquidity_exit_grid_v2(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = ctx or load_analysis_context()
    rows: list[dict[str, Any]] = []
    for rm_thr in LIQ_RM_THRESHOLDS:
        for fm_thr in LIQ_FM_THRESHOLDS:
            dates = _mask_dates(ctx, rm_pct_max=rm_thr, fm_pct_min=fm_thr)
            cell = analyze_cell(
                dates,
                ctx["spx"],
                benchmark=ctx["benchmark"],
                long_side=False,
            )
            rows.append(
                {
                    "pattern": "LIQUIDITY_EXIT",
                    "condition": f"RM_roll_pct<{rm_thr} AND FM_roll_pct>{fm_thr}",
                    "rm_pct_max": rm_thr,
                    "fm_pct_min": fm_thr,
                    **cell,
                }
            )
    return {
        "test_id": "04_liquidity_exit_grid_v2",
        "spec": "rohit_2026-08-04",
        "data_note": ctx["data_note"],
        "fm_distribution": ctx["fm_distribution"],
        "benchmark": ctx["benchmark"],
        "par": run_par_row(ctx),
        "rows": rows,
    }


def run_fm_pctile_regression(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """FM rolling percentile vs SPX forward returns (continuous linear check)."""
    from scipy import stats

    ctx = ctx or load_analysis_context()
    spx, sessions = ctx["spx"], ctx["sessions"]
    horizons = {"1w": 5, "2w": 10, "4w": 20, "8w": 40}
    rows = []
    for dt in ctx["weekly_index"]:
        pct = float(ctx["fm_pct"].loc[dt])
        row: dict[str, Any] = {"date": str(dt.date()), "fm_pctile": pct}
        for label, days in horizons.items():
            from src.macro_intelligence.engine.forward_returns import forward_return_pct

            row[f"ret_{label}"] = forward_return_pct(spx, dt, days, sessions=sessions)
        rows.append(row)
    df = pd.DataFrame(rows).dropna()
    results = []
    for label in horizons:
        y = df[f"ret_{label}"].values
        x = df["fm_pctile"].values
        slope, intercept, r, p, _ = stats.linregress(x, y)
        results.append(
            {
                "horizon": label,
                "n": len(y),
                "r_squared": round(float(r**2), 6),
                "p_value": round(float(p), 6),
                "slope": round(float(slope), 6),
            }
        )
    return {"test_id": "cftc_fm_pctile_regression", "n": len(df), "rows": results}


def run_robustness_checks(
    ctx: dict[str, Any] | None = None,
    *,
    run_bootstrap: bool = True,
    bootstrap_draws: int = 10_000,
) -> dict[str, Any]:
    """Primary robustness: 12-offset weekly subsample stability; optional block bootstrap."""
    ctx = ctx or load_analysis_context()
    cells: list[dict[str, Any]] = []
    for spec in ROBUSTNESS_KEY_CELLS:
        dates = _mask_dates(
            ctx,
            fm_pct_max=spec.get("fm_pct_max"),
            rm_pct_min=spec.get("rm_pct_min"),
            fm_net_max=spec.get("fm_net_max"),
        )
        long_side = bool(spec.get("long_side", True))
        stability = subsample_stability_weekly(
            dates,
            ctx["weekly_index"],
            ctx["spx"],
            benchmark=ctx["benchmark"],
            horizon_label="12w",
            long_side=long_side,
            sessions=ctx["sessions"],
        )
        boot: dict[str, Any] = {}
        if run_bootstrap and len(dates) > 0:
            boot = stationary_block_bootstrap(
                dates,
                ctx["weekly_index"],
                ctx["spx"],
                benchmark=ctx["benchmark"],
                horizon_label="12w",
                block_weeks=12,
                n_draws=bootstrap_draws,
                long_side=long_side,
                sessions=ctx["sessions"],
            )
        cells.append(
            {
                "condition": spec["condition"],
                "n_qualifying_weeks": int(len(dates)),
                "subsample_stability": stability,
                "block_bootstrap": boot,
            }
        )
    return {
        "test_id": "cftc_robustness_subsample",
        "spec": "rohit_subsample_stability_primary",
        "data_note": ctx["data_note"],
        "cells": cells,
    }


def _format_subsample_table(stability: dict[str, Any]) -> list[str]:
    lines = [
        "",
        f"**Full sample ({stability.get('horizon', '12w')}):** "
        f"n_ep={stability.get('full', {}).get('n_episodes')} | "
        f"mean_excess={stability.get('full', {}).get('mean_excess')}% | "
        f"hit_excess={stability.get('full', {}).get('hit_excess_pct')}% | "
        f"offsets_positive={stability.get('offsets_positive_excess')}/{stability.get('offsets_with_data')} | "
        f"stable={stability.get('stable_across_offsets')}",
        "",
        "| Offset | n_ep | mean % | mean excess % | hit % | excess hit % |",
        "|--------|------|--------|---------------|-------|--------------|",
    ]
    for row in stability.get("offsets", []):
        lines.append(
            f"| {row.get('offset')} | {row.get('n_episodes')} | "
            f"{row.get('mean', '—')} | {row.get('mean_excess', '—')} | "
            f"{row.get('hit_pct', '—')} | {row.get('hit_excess_pct', '—')} |"
        )
    spread = stability.get("offset_excess_spread")
    if spread is not None:
        lines.append("")
        lines.append(f"Offset mean-excess spread: **{spread}%**")
    return lines


def _format_bootstrap_section(boot: dict[str, Any]) -> list[str]:
    if not boot or boot.get("n_successful_draws", 0) == 0:
        return ["", "*Block bootstrap: not run or insufficient data.*"]
    b = boot.get("bootstrap_mean_excess", {})
    lines = [
        "",
        "**Stationary block bootstrap** (Politis–Romano, block≈12w, "
        f"{boot.get('n_draws')} draws):",
        f"- Observed mean excess: **{boot.get('observed', {}).get('mean_excess')}%** "
        f"(n_ep={boot.get('observed', {}).get('n_episodes')})",
        f"- Bootstrap percentile of observed: **{b.get('pctile_of_observed')}**",
        f"- Bootstrap null: mean={b.get('mean')}% med={b.get('median')}% "
        f"p5={b.get('p5')}% p95={b.get('p95')}%",
    ]
    ep_pct = boot.get("episode_excess_percentiles", [])
    if ep_pct:
        lines += ["", "| Episode date | 12w excess % | Bootstrap pctile |", "|--------------|--------------|-------------------|"]
        for ep in ep_pct[:20]:
            lines.append(
                f"| {ep.get('date')} | {ep.get('excess')} | {ep.get('bootstrap_pctile')} |"
            )
        if len(ep_pct) > 20:
            lines.append(f"| … | +{len(ep_pct) - 20} more episodes | |")
    return lines


def build_robustness_report(robustness: dict[str, Any]) -> str:
    lines = [
        "# CFTC robustness — non-overlapping subsample stability (PRIMARY)",
        "",
        f"Generated: {stamp()}",
        "",
        "Method: partition analysis calendar into 12 non-overlapping subsamples "
        "(every 12th week at offsets 0–11). Re-run episode collapse + 12w SPX "
        "metrics at each offset. **Stable** = positive mean excess at ≥8 offsets "
        "and ≥67% of offsets with data.",
        "",
        f"- {robustness.get('data_note', '')}",
        "",
    ]
    for cell in robustness.get("cells", []):
        lines.append(f"## `{cell.get('condition')}` (n_qual_weeks={cell.get('n_qualifying_weeks')})")
        lines += _format_subsample_table(cell.get("subsample_stability", {}))
        lines += _format_bootstrap_section(cell.get("block_bootstrap", {}))
    lines += [
        "",
        "## Interpretation guide",
        "",
        "- **Clustered episode:** strong at offset 0 only, collapses at offsets 3+7 → one-time cluster.",
        "- **Real signal:** holds across most/all 12 offsets with similar mean excess.",
        "- Bootstrap percentile near 50 = indistinguishable from resampled null; >90 or <10 = tail outcome.",
        "",
    ]
    return "\n".join(lines)


def build_cftc_grid_summary_md(squeeze: dict, liq: dict, *, horizon: str = "12w") -> str:
    """Validation-suite snippet: par row first, then distribution per cell ranked on mean−median gap."""
    squeeze_rows = [r for r in squeeze["rows"] if r.get("pattern") == "SQUEEZE"]
    ranked = rank_cells_by_gap(squeeze_rows, horizon, squeeze_only=True)
    best = ranked[0] if ranked else None
    lines = [
        "# Tests 3–4: CFTC grids",
        "",
        "Episode-collapsed distribution per conditioned cell. **Rank on mean−median gap** (tail marker).",
        "PAR row = every week in sample, no filter, no episode collapse.",
        "",
    ]
    lines += format_par_section(
        squeeze.get("par", {}),
        benchmark=squeeze.get("benchmark"),
        horizons=["4w", "8w", horizon],
    )
    lines += [
        worked_examples_section(),
        f"## SQUEEZE — top cells by mean−median gap at {horizon}",
        "",
        distribution_table_header(include_instances=True),
        distribution_table_sep(include_instances=True),
    ]
    for row in ranked[:15]:
        lines.append(distribution_table_line(row, horizon, include_instances=True))
    if best:
        m = best.get("metrics", {}).get(horizon, {})
        par_m = squeeze.get("par", {}).get("metrics", {}).get(horizon, {})
        lines += [
            "",
            f"**Highest {horizon} mean−median gap (SQUEEZE rolling cells):** "
            f"`{best.get('condition')}` — n_ep={best.get('n_episodes')} (wk={best.get('n_weeks')}), "
            f"gap={m.get('mean_median_gap')}%, excess_hit={m.get('hit_excess_pct')}%.",
            f"**PAR {horizon} excess_hit:** {par_m.get('hit_excess_pct')}% "
            f"(mean_excess {par_m.get('mean_excess')}%).",
        ]
    lines += [
        "",
        f"## SQUEEZE heatmap — {horizon} avg SPX % / excess_hit %",
        "",
        "| FM < | RM > 40 | RM > 45 | RM > 50 | RM > 55 | RM > 60 | RM > 65 |",
        "|------|-----------|-----------|-----------|-----------|-----------|----------|",
    ]
    for fm in SQUEEZE_FM_THRESHOLDS:
        cells = []
        for rm in SQUEEZE_RM_THRESHOLDS:
            row = next(
                (
                    x
                    for x in squeeze_rows
                    if x.get("fm_pct_max") == fm and x.get("rm_pct_min") == rm
                ),
                None,
            )
            cells.append(format_heatmap_cell(row, horizon))
        lines.append(f"| {fm} | " + " | ".join(cells) + " |")
    lines += ["", "## LIQUIDITY EXIT — top cells by mean−median gap at 4w (short side)", ""]
    for row in rank_cells_by_gap(liq["rows"], "4w", long_side=False)[:10]:
        lines.append(f"- `{row.get('condition')}`: {format_cell_line(row, '4w')}")
        lines.append(f"  - top: {format_episode_instances(row, '4w')}")
    return "\n".join(lines) + "\n"


def _ascii_histogram(values: np.ndarray, *, bins: int = 24) -> list[str]:
    if len(values) == 0:
        return ["(no data)"]
    lo, hi = float(values.min()), float(values.max())
    if lo == hi:
        return [f"  all values = {lo:,.0f}"]
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(values, bins=edges)
    max_c = int(counts.max()) or 1
    width = 48
    lines: list[str] = []
    for i, c in enumerate(counts):
        if c == 0:
            continue
        left = edges[i]
        bar = "#" * max(1, int(c / max_c * width))
        side = "long" if left >= 0 else "short"
        lines.append(f"  {left/1000:6.0f}k |{bar:<{width}}| {c:4d} ({side})")
    return lines


def build_fm_distribution_report(ctx: dict[str, Any]) -> tuple[str, Path | None]:
    """FM net fixed distribution + histogram (Rohit §4 pre-grid)."""
    fm = ctx["fm"].dropna()
    cuts = ctx["fm_distribution"]
    diag = ctx.get("sample_diagnostics", {})
    arr = fm.values.astype(float)
    short_pct = 100.0 * float(np.sum(arr < 0)) / len(arr) if len(arr) else 0.0
    lines = [
        "# CFTC Fast Money Net Position — Fixed Distribution (for Rohit sign-off)",
        "",
        f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d')}",
        "**Series:** CFTC TFF · S&P 500 (legacy STOCK INDEX → Consolidated stitch) · Leveraged Money",
        f"**Sample:** {diag.get('raw_start', fm.index.min().date())} → "
        f"{diag.get('raw_end', fm.index.max().date())} · **n = {cuts.get('n', len(fm))}** weekly observations",
        "",
        "## Sample start (answers Rohit row 75)",
        "",
        f"- Raw TFF FM/RM weekly prints from **{diag.get('raw_start', '—')}**",
        f"- First rolling percentile (≥20 obs): **{diag.get('first_pctile_20obs', '—')}**",
        f"- First **full 156-week** rolling window: **{diag.get('first_full_156w_window', '—')}**",
        f"- Grid analysis weeks: **{diag.get('analysis_weeks', '—')}** "
        f"({diag.get('analysis_start', '—')} → {diag.get('analysis_end', '—')})",
        "- **GFC 2008:** raw FM net exists (104 weeks in 2008–09) but **rolling-percentile grids exclude Sep 2008–May 2009** "
        "because the 156-week window is not full until mid-2009. Rebuild from 2003 would require legacy COT proxy "
        "(pre-TFF non-commercial) — not in current TFF pipeline.",
        "",
        "## Fixed distribution percentiles (contracts)",
        "",
        "| Percentile | FM net (contracts) |",
        "|------------|-------------------:|",
        f"| min | {cuts.get('min', 0):,.0f} |",
        f"| **2.5th** | **{cuts.get('p2_5', 0):,.0f}** |",
        f"| **5th** | **{cuts.get('p5', 0):,.0f}** |",
        f"| **10th** | **{cuts.get('p10', 0):,.0f}** |",
        f"| median | {cuts.get('median', 0):,.0f} |",
        f"| max | {cuts.get('max', 0):,.0f} |",
        "",
        f"**Sign mix:** {short_pct:.1f}% net short · {100 - short_pct:.1f}% net long.",
        "",
    ]
    png_path: Path | None = None
    try:
        import matplotlib.pyplot as plt

        GENERATED_DOCS.mkdir(parents=True, exist_ok=True)
        png_path = GENERATED_DOCS / f"cftc_fm_net_distribution_histogram_{stamp()}.png"
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(arr / 1000, bins=30, color="#2563eb", edgecolor="white")
        ax.axvline(0, color="#dc2626", linestyle="--", linewidth=1)
        for label, key in [("2.5th", "p2_5"), ("5th", "p5"), ("10th", "p10")]:
            if cuts.get(key) is not None:
                ax.axvline(cuts[key] / 1000, color="#64748b", linestyle=":", label=f"{label}")
        ax.set_xlabel("FM net (thousands of contracts)")
        ax.set_ylabel("Week count")
        ax.set_title("CFTC Fast Money net — fixed distribution (full sample)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(png_path, dpi=120)
        plt.close(fig)
        lines.append(f"PNG histogram: `{png_path.relative_to(GENERATED_DOCS.parent.parent)}`")
    except Exception:
        lines.append("_(PNG histogram skipped — matplotlib unavailable)_")
    lines += ["", "## Histogram (ASCII)", ""]
    lines.extend(_ascii_histogram(arr))
    lines += [
        "",
        "## Proposed AND conditions for grid",
        "",
        "| Variant | Condition |",
        "|---------|-----------|",
        "| Baseline | `FM net < 0` |",
        f"| Fixed 5th | `FM net < {cuts.get('p5', 0):,.0f}` |",
        f"| Fixed 10th | `FM net < {cuts.get('p10', 0):,.0f}` |",
        "| Combined | `roll<10 AND net<0` |",
        "",
    ]
    return "\n".join(lines) + "\n", png_path


def build_rohit_report(squeeze: dict, liq: dict, regression: dict, robustness: dict | None = None) -> str:
    squeeze_rows = [r for r in squeeze["rows"] if r.get("pattern") == "SQUEEZE"]
    lines = [
        "# CFTC SQUEEZE / LIQUIDITY EXIT — Rohit re-run (Aug 2026 spec)",
        "",
        f"Generated: {stamp()}",
        "",
        worked_examples_section(),
        "## Data coverage",
        "",
        f"- {squeeze.get('data_note', '')}",
        f"- FM net distribution (fixed, full sample): `{squeeze.get('fm_distribution')}`",
    ]
    diag = squeeze.get("sample_diagnostics") or {}
    if diag:
        lines += [
            "- **Sample start (Rohit row 75):**",
            f"  - Raw TFF from **{diag.get('raw_start')}**; first rolling pctile **{diag.get('first_pctile_20obs')}**;",
            f"  first full 156w window **{diag.get('first_full_156w_window')}**.",
            "  - **GFC 2008 rolling grids:** Sep 2008–May 2009 excluded (156w window not full until ~Jun 2009).",
            "    Raw FM net exists for GFC; percentile-conditioned cells do not.",
            "  - **2003 rebuild:** TFF Lev Money exists from 2006 only; pre-2006 needs legacy COT proxy (deferred).",
            "",
        ]
    else:
        lines += [
            "- **Rolling-percentile grids** require a full 156-week history; earliest valid cells ~2009.",
            "",
        ]
    lines += format_par_section(
        squeeze.get("par", {}),
        benchmark=squeeze.get("benchmark"),
        horizons=list(DEFAULT_HORIZONS.keys()),
        title="§6a PAR row (unconditional — every week in sample, no episode collapse)",
    )
    lines += [
        "## SQUEEZE — top cells by mean−median gap at 12w (rank metric; read with dated instances)",
        "",
        distribution_table_header(include_instances=True),
        distribution_table_sep(include_instances=True),
    ]
    for row in rank_cells_by_gap(squeeze_rows, "12w", positive_gap=True, squeeze_only=True)[:15]:
        lines.append(distribution_table_line(row, "12w", include_instances=True))
    if not rank_cells_by_gap(squeeze_rows, "12w", positive_gap=True, squeeze_only=True):
        lines.append(
            "| — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |"
        )
        lines.append("")
        lines.append("- No rolling-percentile cell with positive 12w mean−median gap and n_ep≥3.")
    lines += [
        "",
        "## SQUEEZE — all rolling cells by mean−median gap at 12w (reference)",
        "",
        distribution_table_header(),
        distribution_table_sep(),
    ]
    for row in rank_cells_by_gap(squeeze_rows, "12w", squeeze_only=True)[:20]:
        lines.append(distribution_table_line(row, "12w"))
    lines += ["", "## SQUEEZE — tight FM rolling percentiles (Rohit §2)", ""]
    lines.append("| FM roll pct | RM>40 12w | RM>45 12w | RM>50 12w |")
    lines.append("|-------------|-----------|-----------|-----------|")
    for fm in [5, 7.5, 10, 12.5, 15, 20]:
        cells = []
        for rm in [40, 45, 50]:
            row = next(
                (
                    x
                    for x in squeeze["rows"]
                    if x.get("fm_pct_max") == fm and x.get("rm_pct_min") == rm and x.get("pattern") == "SQUEEZE"
                ),
                None,
            )
            m = row.get("metrics", {}).get("12w", {}) if row else {}
            cells.append(
                f"n={row.get('n_episodes', 0)} gap={m.get('mean_median_gap', '—')}" if row else "—"
            )
        lines.append(f"| <{fm} | " + " | ".join(cells) + " |")
    lines += ["", "## SQUEEZE absolute cuts (Rohit §4)", ""]
    for r in squeeze["rows"]:
        if r.get("pattern") != "SQUEEZE_ABS":
            continue
        lines.append(f"- `{r.get('condition')}`: {format_cell_line(r, '12w')}")
    lines += ["", "## LIQUIDITY EXIT — top cells by mean−median gap at 4w (short side)", ""]
    for r in rank_cells_by_gap(liq["rows"], "4w", long_side=False)[:15]:
        lines.append(f"- `{r.get('condition')}`: {format_cell_line(r, '4w')}")
        lines.append(f"  - top: {format_episode_instances(r, '4w')}")
    lines += ["", "## LIQUIDITY EXIT — FM>70 vs FM>75 episode dates (Rohit §7)", ""]
    for rm_thr in [20, 25, 30]:
        for fm_thr in [70, 75]:
            row = next(
                (
                    x
                    for x in liq["rows"]
                    if x.get("rm_pct_max") == rm_thr and x.get("fm_pct_min") == fm_thr
                ),
                None,
            )
            if not row:
                continue
            lines.append(f"### RM<{rm_thr} FM>{fm_thr} (n_ep={row.get('n_episodes')})")
            for ep in row.get("episodes", [])[:12]:
                lines.append(
                    f"- {ep.get('date')}: 4w={ep.get('ret_4w')}% excess_4w={ep.get('excess_4w')}% "
                    f"8w={ep.get('ret_8w')}% 12w={ep.get('ret_12w')}%"
                )
    lines += ["", "## FM percentile → SPX linear regression (continuous contrarian check)", ""]
    lines.append("| Horizon | n | R² | p-value | slope |")
    lines.append("|---------|---|-----|---------|-------|")
    for r in regression.get("rows", []):
        lines.append(
            f"| {r['horizon']} | {r['n']} | {r['r_squared']} | {r['p_value']} | {r['slope']} |"
        )
    if robustness:
        lines += [
            "",
            "## PRIMARY robustness — 12-offset subsample stability (FM<7.5 focus)",
            "",
            "Every 12th week × 12 offsets; see full tables in `cftc_robustness_subsample_*.md`.",
            "",
        ]
        for cell in robustness.get("cells", []):
            stab = cell.get("subsample_stability", {})
            full = stab.get("full", {})
            lines.append(f"### `{cell.get('condition')}`")
            lines += _format_subsample_table(stab)
            boot = cell.get("block_bootstrap", {})
            if boot.get("n_successful_draws"):
                b = boot.get("bootstrap_mean_excess", {})
                lines.append(
                    f"- Bootstrap pctile of observed mean excess: **{b.get('pctile_of_observed')}** "
                    f"({boot.get('n_draws')} draws, block≈12w)"
                )
    lines += [
        "",
        "## Sign-off status",
        "",
        "- Rohit Aug 4: **do not sign off** prior grid; this re-run uses episode collapse,",
        "  mean−median gap, excess-over-market (per-episode vs par benchmark), and extended FM axis.",
        "- **PAR row** = every week unconditional; conditioned cells rank vs excess_hit not raw win %.",
        "- **Do not wire into SSI composite** until thresholds confirmed after review.",
        "- Display flags only (panel + Overwatch), no sizing.",
        "",
    ]
    return "\n".join(lines)


def _episode_table_rows(episodes: list[dict[str, Any]], *, sort_key: str = "ret_4w", ascending: bool = True) -> list[str]:
    ranked = sorted(
        [e for e in episodes if e.get(sort_key) is not None],
        key=lambda e: e[sort_key],
        reverse=not ascending,
    )
    rows = [
        "",
        "| Date | 4w SPX % | excess 4w | 8w | 12w |",
        "|------|----------|-----------|-----|-----|",
    ]
    for e in ranked:
        rows.append(
            f"| {e.get('date')} | {e.get('ret_4w')} | {e.get('excess_4w')} | "
            f"{e.get('ret_8w')} | {e.get('ret_12w')} |"
        )
    return rows


def build_tail_episode_dates_report(squeeze: dict, liq: dict) -> str:
    """Full dated episode lists for reported tail findings (Rohit CFTC HIGH)."""
    squeeze_rows = [r for r in squeeze["rows"] if r.get("pattern") == "SQUEEZE"]
    lines = [
        "# CFTC Tail Findings — Dated Episode Lists",
        "",
        f"Generated: {stamp()} | Episode-collapsed (v2), Rohit Aug 2026 spec",
        "",
        "## 1. LIQUIDITY EXIT — FM>70 vs FM>75 discontinuity",
        "",
        "FM>75 is a strict subset of FM>70, yet 4w mean *jumps up* at FM>75 in the sign-off grid.",
        "Mechanism: episodes that **start** when FM rolling pctile is only 70–75 (not yet extreme)",
        "are included in FM>70 but excluded from FM>75. Those dropped episodes have weak 4w returns.",
        "",
        "| RM < | n_ep FM>70 | 4w mean FM>70 | n_ep FM>75 | 4w mean FM>75 | dropped n | dropped 4w mean |",
        "|------|------------|---------------|------------|---------------|-----------|-----------------|",
    ]
    for rm_thr in [20, 25, 30]:
        c70 = next((x for x in liq["rows"] if x.get("rm_pct_max") == rm_thr and x.get("fm_pct_min") == 70), None)
        c75 = next((x for x in liq["rows"] if x.get("rm_pct_max") == rm_thr and x.get("fm_pct_min") == 75), None)
        if not c70 or not c75:
            continue
        eps70 = {e["date"]: e for e in c70.get("all_episodes", [])}
        eps75 = {e["date"]: e for e in c75.get("all_episodes", [])}
        dropped = sorted(set(eps70) - set(eps75))
        dr = [eps70[d]["ret_4w"] for d in dropped if eps70[d].get("ret_4w") is not None]
        dropped_mean = round(float(np.mean(dr)), 4) if dr else None
        m70 = c70["metrics"]["4w"]
        m75 = c75["metrics"]["4w"]
        lines.append(
            f"| {rm_thr} | {c70['n_episodes']} | {m70['mean']} | {c75['n_episodes']} | {m75['mean']} | "
            f"{len(dropped)} | {dropped_mean} |"
        )
    lines.append("")
    for rm_thr in [20, 25, 30]:
        c70 = next((x for x in liq["rows"] if x.get("rm_pct_max") == rm_thr and x.get("fm_pct_min") == 70), None)
        c75 = next((x for x in liq["rows"] if x.get("rm_pct_max") == rm_thr and x.get("fm_pct_min") == 75), None)
        if not c70 or not c75:
            continue
        eps70 = {e["date"]: e for e in c70.get("all_episodes", [])}
        eps75 = {e["date"]: e for e in c75.get("all_episodes", [])}
        dropped = sorted(set(eps70) - set(eps75))
        kept = sorted(set(eps75))
        lines.append(f"### RM<{rm_thr}")
        lines.append("")
        lines.append("**Dropped episodes (FM 70–75 band only, excluded from FM>75):**")
        lines += _episode_table_rows([eps70[d] for d in dropped])
        lines.append("")
        lines.append("**All FM>75 episodes:**")
        lines += _episode_table_rows([eps75[d] for d in kept])
        lines.append("")
    lines += [
        "### Cluster check (independent events vs one crash counted many times)",
        "",
        "Episode collapse already merges consecutive qualifying weeks. Remaining same-month",
        "starts are separate episode onsets (>10 calendar days apart), not duplicate week counts.",
        "",
    ]
    from collections import defaultdict

    for rm_thr in [20, 25, 30]:
        c75 = next((x for x in liq["rows"] if x.get("rm_pct_max") == rm_thr and x.get("fm_pct_min") == 75), None)
        if not c75:
            continue
        dates = sorted(e["date"] for e in c75.get("all_episodes", []))
        clusters: dict[str, list[str]] = defaultdict(list)
        for d in dates:
            clusters[d[:7]].append(d)
        multi = {k: v for k, v in clusters.items() if len(v) > 1}
        lines.append(f"**RM<{rm_thr} FM>75** ({len(dates)} episodes): months with >1 episode start: {len(multi)}")
        for ym, ds in sorted(multi.items()):
            lines.append(f"  - {ym}: {', '.join(ds)}")
        lines.append("")
    lines += ["## 2. SQUEEZE — tail cells (positive 12w mean−median gap, n_ep≥3)", ""]
    for _, row in sorted(
        (
            (r["metrics"]["12w"]["mean_median_gap"], r)
            for r in squeeze_rows
            if (r["metrics"]["12w"].get("mean_median_gap") or 0) > 0 and r["n_episodes"] >= 3
        ),
        key=lambda x: -x[0],
    ):
        m = row["metrics"]["12w"]
        lines.append(f"### `{row['condition']}` — gap={m['mean_median_gap']}%, n_ep={row['n_episodes']}")
        lines.append(
            f"mean={m['mean']}% med={m['median']}% hit={m['hit_pct']}% excess_hit={m['hit_excess_pct']}%"
        )
        lines.append("")
        lines.append("| Date | 12w SPX % | excess 12w | 4w | 8w |")
        lines.append("|------|-----------|------------|-----|-----|")
        for e in sorted(row.get("all_episodes", []), key=lambda x: x.get("ret_12w") or -999, reverse=True):
            lines.append(
                f"| {e['date']} | {e.get('ret_12w')} | {e.get('excess_12w')} | "
                f"{e.get('ret_4w')} | {e.get('ret_8w')} |"
            )
        lines.append("")
    lines += ["## 3. LIQUIDITY EXIT — top tail cells (|mean−median| gap at 4w, n_ep≥3)", ""]
    liq_tail = sorted(
        (
            (abs(r["metrics"]["4w"]["mean_median_gap"]), r["metrics"]["4w"]["mean_median_gap"], r)
            for r in liq["rows"]
            if r["metrics"]["4w"].get("mean_median_gap") is not None and r["n_episodes"] >= 3
        ),
        key=lambda x: -x[0],
    )
    for _, gap, row in liq_tail[:15]:
        m = row["metrics"]["4w"]
        lines.append(f"### `{row['condition']}` — gap={gap}%, n_ep={row['n_episodes']}")
        lines.append(
            f"mean={m['mean']}% med={m['median']}% hit={m['hit_pct']}% excess_hit={m['hit_excess_pct']}%"
        )
        lines += _episode_table_rows(row.get("all_episodes", []), sort_key="ret_4w", ascending=True)
        lines.append("")
    return "\n".join(lines)


def _to_legacy_grid_payload(v2_payload: dict[str, Any], *, pattern: str) -> dict[str, Any]:
    """Map v2 episode metrics to legacy JSON keys for compile script / sign-off report."""
    rows: list[dict[str, Any]] = []
    for r in v2_payload.get("rows", []):
        if pattern == "SQUEEZE" and r.get("pattern") != "SQUEEZE":
            continue
        if pattern == "LIQ" and r.get("pattern") != "LIQUIDITY_EXIT":
            continue
        metrics: dict[str, Any] = {}
        for label, m in (r.get("metrics") or {}).items():
            metrics[label] = {
                "n": m.get("n"),
                "avg": m.get("mean"),
                "median": m.get("median"),
                "win_pct": m.get("hit_pct"),
                "worst": m.get("worst"),
                "sharpe": m.get("sharpe"),
                "mean_excess": m.get("mean_excess"),
                "median_excess": m.get("median_excess"),
                "excess_hit_pct": m.get("hit_excess_pct"),
                "mean_median_gap": m.get("mean_median_gap"),
            }
        row = {
            "n": r.get("n_episodes", 0),
            "n_episodes": r.get("n_episodes", 0),
            "n_weeks": r.get("n_weeks", 0),
            "metrics": metrics,
        }
        if pattern == "SQUEEZE":
            row["fm_max"] = r.get("fm_pct_max")
            row["rm_min"] = r.get("rm_pct_min")
        else:
            row["rm_max"] = r.get("rm_pct_max")
            row["fm_min"] = r.get("fm_pct_min")
        rows.append(row)
    par = v2_payload.get("par", {})
    par_metrics: dict[str, Any] = {}
    for label, m in (par.get("metrics") or {}).items():
        par_metrics[label] = {
            "n": m.get("n"),
            "avg": m.get("mean"),
            "median": m.get("median"),
            "win_pct": m.get("hit_pct"),
            "worst": m.get("worst"),
            "sharpe": m.get("sharpe"),
            "mean_excess": m.get("mean_excess"),
            "median_excess": m.get("median_excess"),
            "excess_hit_pct": m.get("hit_excess_pct"),
        }
    par_row = {
        "condition": "PAR (all weeks, unconditional)",
        "n": par.get("n_weeks", 0),
        "n_episodes": par.get("n_episodes", 0),
        "n_weeks": par.get("n_weeks", 0),
        "metrics": par_metrics,
    }
    test_id = "03_squeeze_grid" if pattern == "SQUEEZE" else "04_liquidity_exit_grid"
    return {
        "test_id": test_id,
        "benchmark": v2_payload.get("benchmark"),
        "par": par_row,
        "rows": rows,
    }


def run_and_report(start: str = "2006-01-01", *, run_bootstrap: bool = True) -> dict[str, Any]:
    ctx = load_analysis_context(start=start, pctile_start="2006-01-01")
    squeeze = run_squeeze_grid_v2(ctx)
    liq = run_liquidity_exit_grid_v2(ctx)
    regression = run_fm_pctile_regression(ctx)
    robustness = run_robustness_checks(ctx, run_bootstrap=run_bootstrap)
    save_artifact("03_squeeze_grid", _to_legacy_grid_payload(squeeze, pattern="SQUEEZE"))
    save_artifact("04_liquidity_exit_grid", _to_legacy_grid_payload(liq, pattern="LIQ"))
    save_artifact("03_squeeze_grid_v2", squeeze)
    save_artifact("04_liquidity_exit_grid_v2", liq)
    save_artifact("cftc_fm_pctile_regression", regression)
    save_artifact("cftc_robustness_subsample", robustness)
    fm_dist_md, fm_dist_png = build_fm_distribution_report(ctx)
    fm_dist_path = write_md_snippet("cftc_fm_net_distribution_for_rohit", fm_dist_md)
    md = build_rohit_report(squeeze, liq, regression, robustness)
    md_path = write_md_snippet("cftc_rohit_rerun", md)
    tail_md = build_tail_episode_dates_report(squeeze, liq)
    tail_path = write_md_snippet("cftc_tail_episode_dates", tail_md)
    robustness_md = build_robustness_report(robustness)
    robustness_path = write_md_snippet("cftc_robustness_subsample", robustness_md)
    summary_md = build_cftc_grid_summary_md(squeeze, liq)
    write_md_snippet("03_04_cftc_grid", summary_md)
    return {
        "squeeze": squeeze,
        "liquidity": liq,
        "regression": regression,
        "robustness": robustness,
        "report_md": str(md_path),
        "tail_episodes_md": str(tail_path),
        "robustness_md": str(robustness_path),
        "fm_distribution_md": str(fm_dist_path),
        "fm_distribution_png": str(fm_dist_png) if fm_dist_png else None,
    }
