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
    SIDE_CONVENTION_NOTE,
    horizon_metrics,
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


# CFTC redefined the Consolidated line here (see cftc_pull._emini_equivalent_series). The series
# is restated so it is no longer a seam in the data, but it stays the split date for the standing
# stability test: Rohit's rule is that a cell which only works on one side of it does not work.
SEAM_DATE = pd.Timestamp("2023-05-02")


def split_stability(
    ctx: dict[str, Any],
    dates: pd.DatetimeIndex,
    *,
    horizon: str = "12w",
    long_side: bool = True,
    split_at: pd.Timestamp = SEAM_DATE,
) -> dict[str, Any]:
    """Re-run a cell separately either side of ``split_at`` (Rohit's standing test).

    He found FM<10/RM>55 carried by its post-2023 block -- 13 of 21 episodes, all of the positive
    excess -- while the pre-2023 side ran at half of par with negative excess. Reporting only the
    combined number hides that, so every cell that gets recommended now carries this split.
    """
    out: dict[str, Any] = {"split_at": str(pd.Timestamp(split_at).date()), "horizon": horizon}
    for tag, sel in (
        ("pre", dates[dates < split_at]),
        ("post", dates[dates >= split_at]),
        ("all", dates),
    ):
        if len(sel) == 0:
            out[tag] = {"n_weeks": 0, "n_episodes": 0}
            continue
        cell = analyze_cell(
            pd.DatetimeIndex(sel), ctx["spx"], benchmark=ctx["benchmark"],
            long_side=long_side, sessions=ctx["sessions"], top_episodes=0,
        )
        m = (cell.get("metrics") or {}).get(horizon, {})
        out[tag] = {
            "n_weeks": cell.get("n_weeks", 0),
            "n_episodes": cell.get("n_episodes", 0),
            "mean": m.get("mean"),
            "mean_excess": m.get("mean_excess"),
            "hit_excess_pct": m.get("hit_excess_pct"),
        }
    pre, post = out.get("pre", {}), out.get("post", {})
    both_sides = bool(pre.get("n_episodes")) and bool(post.get("n_episodes"))
    signs = [s.get("mean_excess") for s in (pre, post) if s.get("mean_excess") is not None]
    out["fires_both_sides"] = both_sides
    out["consistent_sign"] = bool(len(signs) == 2 and (signs[0] > 0) == (signs[1] > 0))
    out["survives_split"] = bool(both_sides and out["consistent_sign"])
    return out


def _episode_signature(row: dict[str, Any]) -> tuple[str, ...]:
    eps = row.get("all_episodes") or row.get("episodes") or []
    return tuple(sorted(str(e.get("date")) for e in eps if e.get("date")))


def flag_duplicate_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group cells that fire on exactly the same episodes.

    Rohit: "FM<5 / RM>55, >60 and >65 are the same six episodes printed three times. Not three
    corroborating cells." Three cells agreeing is evidence; one cell printed three times is not,
    and the reader cannot tell them apart from the grid alone.
    """
    groups: dict[tuple[str, ...], list[str]] = {}
    for row in rows:
        sig = _episode_signature(row)
        if not sig:
            continue
        groups.setdefault(sig, []).append(str(row.get("condition")))
    dupes = []
    for sig, conditions in groups.items():
        if len(conditions) > 1:
            dupes.append(
                {"n_episodes": len(sig), "episodes": list(sig), "conditions": sorted(conditions)}
            )
    return sorted(dupes, key=lambda d: -len(d["conditions"]))


def run_par_row(ctx: dict[str, Any]) -> dict[str, Any]:
    return analyze_par_row(
        ctx["weekly_index"],
        ctx["spx"],
        benchmark=ctx["benchmark"],
        sessions=ctx["sessions"],
    )


def rank_cells_by_excess_hit(
    rows: list[dict[str, Any]],
    *,
    horizon: str = "12w",
    pattern: str | None = None,
    min_episodes: int = 3,
    par: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank on excess-hit, which is the number Rohit said on 4 Aug he would actually look at.

    The 4 Aug spec asked for mean-median gap as the *tail* marker, and the report ranked on it
    alone -- which is how the recommendation ended up on FM<10/RM>55 while the report's own
    excess-hit table put FM<12.5 above it on every RM column. Both orderings are published now,
    and cells below par on excess-hit are marked rather than silently ranked.
    """
    par_hit = None
    if par:
        par_hit = ((par.get("metrics") or {}).get(horizon) or {}).get("hit_excess_pct")
        if par_hit is None:
            par_hit = ((par.get("metrics") or {}).get(horizon) or {}).get("excess_hit_pct")
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        if pattern is not None and row.get("pattern") != pattern:
            continue
        m = horizon_metrics(row, horizon)
        hit = m.get("hit_excess_pct")
        if hit is None or (m.get("n") or 0) < min_episodes:
            continue
        row["beats_par_excess_hit"] = None if par_hit is None else bool(hit > par_hit)
        scored.append((float(hit), row))
    scored.sort(key=lambda x: -x[0])
    return [row for _, row in scored]


def _seam_split_for_top_cells(
    ctx: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    pattern: str,
    par: dict[str, Any] | None = None,
    horizon: str | None = None,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Run the pre/post split on every cell a reader might act on, not on a hand-picked list."""
    long_side = pattern != "LIQUIDITY_EXIT"
    horizon = horizon or ("12w" if long_side else "4w")
    grid_rows = [r for r in rows if r.get("pattern") == pattern]
    by_hit = rank_cells_by_excess_hit(
        grid_rows, horizon=horizon, pattern=pattern, par=par
    )[:top_n]
    by_gap = rank_cells_by_gap(grid_rows, horizon, long_side=long_side)[:top_n]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in by_hit + by_gap:
        cond = str(row.get("condition"))
        if cond in seen:
            continue
        seen.add(cond)
        if long_side:
            dates = _mask_dates(ctx, fm_pct_max=row.get("fm_pct_max"), rm_pct_min=row.get("rm_pct_min"))
        else:
            dates = _mask_dates(ctx, rm_pct_max=row.get("rm_pct_max"), fm_pct_min=row.get("fm_pct_min"))
        split = split_stability(ctx, dates, horizon=horizon, long_side=long_side)
        out.append({"condition": cond, **split})
    return out


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
    # FM as a share of open interest (Rohit §4). A fixed contract-count cut is not comparable
    # across twenty years of growth in the venue -- and on the old series it was not even
    # comparable across 2023, because the fixed distribution was computed across the unit change,
    # so fixed_p10 returned 106 weeks that were all post-May-2023. A ratio has neither problem.
    ratio = ctx.get("fm_over_oi")
    if ratio is not None and not ratio.empty:
        idx = ctx["weekly_index"]
        aligned = ratio.reindex(idx).dropna()
        for pct_val in (2.5, 5.0, 10.0):
            if aligned.empty:
                break
            cut = float(np.percentile(aligned.values, pct_val))
            dates = pd.DatetimeIndex(aligned.index[aligned <= cut])
            if len(dates) == 0:
                continue
            cell = analyze_cell(dates, ctx["spx"], benchmark=ctx["benchmark"], long_side=True)
            rows.append(
                {
                    "pattern": "SQUEEZE_ABS",
                    "condition": f"FM_net/open_interest <= p{pct_val} ({cut:.4f})",
                    "fm_over_oi_pctile": pct_val,
                    "fm_over_oi_cut": round(cut, 6),
                    **cell,
                }
            )
    par = run_par_row(ctx)
    return {
        "test_id": "03_squeeze_grid_v2",
        "spec": "rohit_2026-08-24",
        "data_note": ctx["data_note"],
        "sample_diagnostics": ctx.get("sample_diagnostics"),
        "fm_distribution": ctx["fm_distribution"],
        "benchmark": ctx["benchmark"],
        "par": par,
        "rows": rows,
        "duplicate_cells": flag_duplicate_cells([r for r in rows if r.get("pattern") == "SQUEEZE"]),
        "seam_split": _seam_split_for_top_cells(ctx, rows, pattern="SQUEEZE", par=par),
    }


def leg_availability(ctx: dict[str, Any], *, split_at: pd.Timestamp = SEAM_DATE) -> dict[str, Any]:
    """Why a pattern is silent: which *leg* stopped being satisfiable, and when.

    LIQUIDITY EXIT has not fired since 2022, and the natural reading was that the FM unit seam
    pinned the FM percentile so a high-FM condition could never trigger. Restating the units does
    not bring the pattern back, so that reading is incomplete -- this reports each leg separately
    so the silence is attributed to the leg that actually caused it rather than assumed.
    """
    idx = ctx["weekly_index"]
    fm_pct, rm_pct = ctx["fm_pct"].loc[idx], ctx["rm_pct"].loc[idx]
    legs = {
        "FM_pct>45": fm_pct > 45,
        "FM_pct>70": fm_pct > 70,
        "RM_pct<30": rm_pct < 30,
        "RM_pct<15": rm_pct < 15,
    }
    out: dict[str, Any] = {"split_at": str(pd.Timestamp(split_at).date()), "legs": []}
    for name, mask in legs.items():
        fired = idx[mask.values]
        pre = mask[idx < split_at]
        post = mask[idx >= split_at]
        out["legs"].append(
            {
                "leg": name,
                "pre_pct_of_weeks": round(100.0 * float(pre.mean()), 1) if len(pre) else None,
                "post_pct_of_weeks": round(100.0 * float(post.mean()), 1) if len(post) else None,
                "last_fired": str(fired.max().date()) if len(fired) else None,
                "weeks_since_last_fired": int((idx.max() - fired.max()).days // 7) if len(fired) else None,
            }
        )
    return out


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
    par = run_par_row(ctx)
    return {
        "test_id": "04_liquidity_exit_grid_v2",
        "spec": "rohit_2026-08-24",
        "data_note": ctx["data_note"],
        "sample_diagnostics": ctx.get("sample_diagnostics"),
        "fm_distribution": ctx["fm_distribution"],
        "benchmark": ctx["benchmark"],
        "par": par,
        "rows": rows,
        "duplicate_cells": flag_duplicate_cells(rows),
        "seam_split": _seam_split_for_top_cells(ctx, rows, pattern="LIQUIDITY_EXIT", par=par),
        "leg_availability": leg_availability(ctx),
    }


REGRESSION_HORIZONS = {"1w": 5, "2w": 10, "4w": 20, "8w": 40}


def run_fm_pctile_regression(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """FM rolling percentile vs SPX forward returns (continuous linear check)."""
    from scipy import stats

    ctx = ctx or load_analysis_context()
    spx, sessions = ctx["spx"], ctx["sessions"]
    horizons = REGRESSION_HORIZONS
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


def _pctile_forward_frame(ctx: dict[str, Any], horizons: dict[str, int]) -> pd.DataFrame:
    """One row per analysis week: FM pct, RM pct, and SPX forward returns."""
    from src.macro_intelligence.engine.forward_returns import forward_return_pct

    spx, sessions = ctx["spx"], ctx["sessions"]
    rows = []
    for dt in ctx["weekly_index"]:
        row: dict[str, Any] = {
            "date": str(dt.date()),
            "fm_pctile": float(ctx["fm_pct"].loc[dt]),
            "rm_pctile": float(ctx["rm_pct"].loc[dt]),
        }
        for label, days in horizons.items():
            row[f"ret_{label}"] = forward_return_pct(spx, dt, days, sessions=sessions)
        rows.append(row)
    return pd.DataFrame(rows).dropna()


def run_rm_pctile_regression(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """RM rolling percentile vs SPX forward returns — the mirror of the FM test.

    Rohit 4 Aug point 2 asks whether RM has explanatory power at all. Same horizons, same
    ``linregress`` shape as ``run_fm_pctile_regression`` so the two tables can be read side by
    side rather than argued about.
    """
    from scipy import stats

    ctx = ctx or load_analysis_context()
    horizons = REGRESSION_HORIZONS
    df = _pctile_forward_frame(ctx, horizons)
    results = []
    for label in horizons:
        y = df[f"ret_{label}"].values
        x = df["rm_pctile"].values
        slope, _intercept, r, p, _ = stats.linregress(x, y)
        results.append(
            {
                "horizon": label,
                "n": len(y),
                "r_squared": round(float(r**2), 6),
                "p_value": round(float(p), 6),
                "slope": round(float(slope), 6),
            }
        )
    return {"test_id": "cftc_rm_pctile_regression", "n": len(df), "rows": results}


def run_joint_pctile_regression(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """FM and RM together — does RM add anything *on top of* FM?

    A single-variable test can only say whether RM is significant alone. The question that decides
    whether RM stays in the SQUEEZE condition is incremental: fit forward return on FM alone and on
    FM + RM, and report the change in adjusted R-squared with each coefficient's p-value. OLS by
    normal equations (numpy) rather than a new dependency.
    """
    from scipy import stats

    ctx = ctx or load_analysis_context()
    horizons = REGRESSION_HORIZONS
    df = _pctile_forward_frame(ctx, horizons)
    n = len(df)
    results = []
    for label in horizons:
        y = df[f"ret_{label}"].values
        fm = df["fm_pctile"].values
        rm = df["rm_pctile"].values

        _, _, r_fm, p_fm_only, _ = stats.linregress(fm, y)
        r2_fm = float(r_fm**2)
        adj_r2_fm = 1 - (1 - r2_fm) * (n - 1) / (n - 2) if n > 2 else float("nan")

        design = np.column_stack([np.ones(n), fm, rm])
        coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
        resid = y - design @ coeffs
        ss_res = float(resid @ resid)
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2_joint = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        adj_r2_joint = 1 - (1 - r2_joint) * (n - 1) / (n - 3) if n > 3 else float("nan")

        # Coefficient p-values from the OLS covariance matrix.
        dof = n - 3
        sigma2 = ss_res / dof if dof > 0 else float("nan")
        cov = sigma2 * np.linalg.inv(design.T @ design)
        se = np.sqrt(np.diag(cov))
        t_stats = coeffs / se
        p_values = [float(2 * (1 - stats.t.cdf(abs(t), dof))) for t in t_stats]

        results.append(
            {
                "horizon": label,
                "n": n,
                "r_squared_fm_only": round(r2_fm, 6),
                "adj_r_squared_fm_only": round(float(adj_r2_fm), 6),
                "p_value_fm_only": round(float(p_fm_only), 6),
                "r_squared_joint": round(float(r2_joint), 6),
                "adj_r_squared_joint": round(float(adj_r2_joint), 6),
                "delta_adj_r_squared": round(float(adj_r2_joint - adj_r2_fm), 6),
                "coef_fm": round(float(coeffs[1]), 6),
                "p_value_fm": round(p_values[1], 6),
                "coef_rm": round(float(coeffs[2]), 6),
                "p_value_rm": round(p_values[2], 6),
            }
        )
    return {"test_id": "cftc_joint_pctile_regression", "n": n, "rows": results}


def run_rm_increment_cells(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """The same FM cut with and without the RM leg — the number Rohit's point 2 turns on.

    "RM may be doing all the work" is testable directly: hold FM<10 (and FM<5) fixed, then add the
    RM>55 condition and see what the episode count, the mean-minus-median gap and the excess over
    the PAR row actually do. If RM only removes episodes without improving the gap, it is a filter
    that costs sample and buys nothing.
    """
    ctx = ctx or load_analysis_context()
    rows: list[dict[str, Any]] = []
    for fm_thr in (10, 5):
        for rm_thr in (None, 55):
            dates = _mask_dates(ctx, fm_pct_max=fm_thr, rm_pct_min=rm_thr)
            cell = analyze_cell(dates, ctx["spx"], benchmark=ctx["benchmark"], long_side=True)
            rows.append(
                {
                    "condition": (
                        f"FM_roll_pct<{fm_thr}"
                        if rm_thr is None
                        else f"FM_roll_pct<{fm_thr} AND RM_roll_pct>{rm_thr}"
                    ),
                    "fm_pct_max": fm_thr,
                    "rm_pct_min": rm_thr,
                    "rm_leg": rm_thr is not None,
                    **cell,
                }
            )
    return {
        "test_id": "cftc_rm_increment_cells",
        "spec": "rohit_2026-08-13_point_2",
        "benchmark": ctx["benchmark"],
        "par": run_par_row(ctx),
        "rows": rows,
    }


def robustness_specs_for_grid(
    squeeze: dict[str, Any] | None,
    *,
    top_n: int = 4,
    horizon: str = "12w",
) -> list[dict[str, Any]]:
    """Robustness targets taken from the grid's own ranking, plus the fixed key cells.

    Rohit, 24 Aug: "robustness doesn't cover the cell you recommended." It ran on FM<7.5/RM>45,
    FM<7.5/RM>40, FM<7.5&FM_net<0 and FM<5/RM>45 -- a list written before the grid existed --
    while the recommendation was FM<10/RM>55. Deriving the targets from the ranking means the
    cell that gets recommended is always one of the cells that got tested.
    """
    specs = [dict(s) for s in ROBUSTNESS_KEY_CELLS]
    if not squeeze:
        return specs
    grid_rows = [r for r in (squeeze.get("rows") or []) if r.get("pattern") == "SQUEEZE"]
    par = squeeze.get("par")
    ranked = rank_cells_by_excess_hit(grid_rows, horizon=horizon, pattern="SQUEEZE", par=par)[:top_n]
    ranked += rank_cells_by_gap(grid_rows, horizon, long_side=True)[:top_n]
    known = {s["condition"] for s in specs}
    for row in ranked:
        cond = str(row.get("condition"))
        if cond in known:
            continue
        known.add(cond)
        specs.append(
            {
                "condition": cond,
                "fm_pct_max": row.get("fm_pct_max"),
                "rm_pct_min": row.get("rm_pct_min"),
                "long_side": True,
                "source": "grid_ranking",
            }
        )
    return specs


def run_robustness_checks(
    ctx: dict[str, Any] | None = None,
    *,
    run_bootstrap: bool = True,
    bootstrap_draws: int = 10_000,
    specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Primary robustness: 12-offset weekly subsample stability; optional block bootstrap."""
    ctx = ctx or load_analysis_context()
    cells: list[dict[str, Any]] = []
    for spec in (specs or ROBUSTNESS_KEY_CELLS):
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
                "source": spec.get("source", "fixed_key_cell"),
                "n_qualifying_weeks": int(len(dates)),
                "subsample_stability": stability,
                "block_bootstrap": boot,
                "seam_split": split_stability(ctx, dates, horizon="12w", long_side=long_side),
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
        (
            f"Offsets carry a median of **{stability.get('median_episodes_per_offset')}** episodes "
            f"(min {stability.get('min_episodes_per_offset')}). "
            + (
                "That is enough for the agreement across offsets to mean something."
                if stability.get("meaningful_offset_size")
                else "**At that size the offset agreement is arithmetic, not evidence** — twelve subsamples "
                "of two or three episodes will agree on sign often enough by chance, so `stable` is "
                "withheld here regardless of how the signs fall."
            )
        ),
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
        f"**Series:** CFTC TFF · S&P 500 · Leveraged Money · units `{diag.get('unit_basis', 'emini_equivalent')}` "
        "(component contract lines at notional weight — no Consolidated-line stitch, no 2023 unit seam)",
        f"**Sample:** {diag.get('raw_start', fm.index.min().date())} → "
        f"{diag.get('raw_end', fm.index.max().date())} · **n = {cuts.get('n', len(fm))}** weekly observations",
        "",
        "## Sample start — one number, everywhere (Rohit row 75)",
        "",
        f"- Raw TFF FM/RM weekly prints from **{diag.get('raw_start', '—')}**",
        f"- First **full {diag.get('pctile_window_weeks', 156)}-week** window — and therefore the analysis "
        f"start, since partial windows are no longer ranked: **{diag.get('first_full_window', '—')}**",
        f"- Unit-break scan: {diag.get('unit_breaks') or '**none**'}",
        f"- Grid analysis weeks: **{diag.get('analysis_weeks', '—')}** "
        f"({diag.get('analysis_start', '—')} → {diag.get('analysis_end', '—')})",
        "- **GFC 2008:** **not** in the percentile grids, and the earlier wording here saying it was is "
        "withdrawn. Those 2008 cells existed only because `weekly_pctile_series()` would rank a "
        "20-observation window and call the result a 3-year percentile. It now requires a full window, so "
        "the first rankable week is after the crash. Including 2008 needs a shorter window, an explicitly "
        "accepted partial one, or the legacy proxy — a decision, not a code change.",
        "- **Pre-2006:** TFF Leveraged Money starts 2006-06-13. The legacy COT non-commercial series "
        "(2003+) is now built and cached (`fetch_cftc_legacy_noncommercial_net`), but on the 2006–2010 "
        "overlap it tracks TFF only loosely — level corr 0.64, percentile corr 0.54, mean absolute "
        "percentile difference 23 points, and barely half the FM<10 extreme weeks agree. It is therefore "
        "published as labelled context (`legacy_noncommercial`), **not** stitched into these grids.",
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
            "- **Sample start — one number, everywhere:**",
            f"  - Raw TFF weekly prints from **{diag.get('raw_start')}** to **{diag.get('raw_end')}** "
            f"(**{diag.get('raw_weeks')}** weeks).",
            f"  - First **full {diag.get('pctile_window_weeks')}-week** window closes "
            f"**{diag.get('first_full_window')}**, and that *is* the analysis start — partial windows are "
            f"no longer ranked, so there is no second, looser start date to quote. "
            f"Analysis: **{diag.get('analysis_weeks')}** weeks "
            f"({diag.get('analysis_start')} → {diag.get('analysis_end')}).",
            f"  - **Units:** `{diag.get('unit_basis')}`. CFTC redefined the S&P 500 Consolidated line on "
            "2023-05-02 (big-contract equivalents with micro excluded → E-mini equivalents with micro "
            "included), which put a ~5x seam mid-sample in every earlier version of this report. The "
            "series is now summed from the component contract lines at notional weight, so it is "
            "continuous by construction.",
            f"  - **Unit-break scan:** {diag.get('unit_breaks') or '**none** — no week where every field '
            'scales by a common factor.'}",
            "  - **GFC 2008:** **not** in the percentile grids. The first rankable week is "
            f"**{diag.get('first_full_window')}**, after the crash. Earlier statements that the GFC was "
            "included came from ranking partial windows from 20 observations; those ranks were labelled "
            "3-year percentiles but were not. Including 2008 needs a shorter window, an explicitly "
            "accepted partial window, or the legacy proxy — a decision, not a code change.",
            "  - **Pre-2006:** TFF Leveraged Money starts 2006-06-13, so there is nothing to rebuild from "
            "2003 in this definition. The legacy COT non-commercial series is built and cached, but the "
            "2006–2010 overlap (level corr 0.64, pctile corr 0.54, ~half of FM<10 weeks disagree) says it "
            "is not a like-for-like FM substitute — kept as labelled context, not stitched in.",
            "",
        ]
    else:
        lines += [
            "- **Rolling-percentile grids** require a full 156-week history; earliest valid cells ~2009.",
            "",
        ]
    reg_rows = regression.get("rows", [])
    if reg_rows:
        worst_p = max((r.get("p_value") or 0) for r in reg_rows)
        best_r2 = max((r.get("r_squared") or 0) for r in reg_rows)
        lines += [
            "## Executive summary — read this before the grids",
            "",
            f"- **FM percentile has no linear relationship with SPX forward returns.** R² tops out at "
            f"**{best_r2:.4g}** across {len(reg_rows)} horizons, with p-values as weak as **{worst_p:.2g}**; "
            "nothing is significant at any horizon. That does not rule out a threshold effect in the tail "
            "— a linear fit would not show one — but it does settle the row 42 question: at that R², "
            "whether Layer 3 applies `invert=True` to `cot_fast_money` is immaterial either way.",
            "- **Rank cells on excess-hit, not on the mean−median gap alone.** Both orderings are published "
            "below; where they disagree, the excess-hit table is the one to act on, and any cell below the "
            "PAR excess-hit is marked as such.",
            "- **Any cell worth recommending carries a pre/post 2023-05-02 split** (see the seam-stability "
            "section). A cell that only works on one side of that date does not work.",
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
    lines += [
        "",
        "## LIQUIDITY EXIT — top cells by mean−median gap at 4w (short side)",
        "",
        SIDE_CONVENTION_NOTE,
        "",
        distribution_table_header(fm_label="RM <", rm_label="FM >"),
        distribution_table_sep(),
    ]
    liq_top = rank_cells_by_gap(liq["rows"], "4w", long_side=False)[:15]
    for r in liq_top:
        lines.append(
            distribution_table_line(r, "4w", fm_key="rm_pct_max", rm_key="fm_pct_min")
        )
    lines += ["", "### LIQUIDITY EXIT — dated instances for the cells above", ""]
    for r in liq_top:
        lines.append(
            f"- `{r.get('condition')}`: {format_episode_instances(r, '4w', long_side=False)}"
        )
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
    legs = (liq.get("leg_availability") or {}).get("legs") or []
    if legs:
        lines += [
            "",
            "## Why LIQUIDITY EXIT has been silent — it is the RM leg, not the FM units",
            "",
            "The natural reading of four years of silence was that the FM unit seam pinned the FM "
            "percentile low, so a high-FM condition could never fire. Restating the units does not bring "
            "the pattern back. Split by leg, the cause is the **RM** side: asset managers have been "
            "persistently net long since 2023, so a 156-week rank of RM has not been near its floor.",
            "",
            "| leg | % of weeks pre-2023-05-02 | % of weeks post | last fired | weeks since |",
            "|-----|--------------------------:|----------------:|------------|------------:|",
        ]
        for leg in legs:
            lines.append(
                f"| `{leg['leg']}` | {leg.get('pre_pct_of_weeks')} | {leg.get('post_pct_of_weeks')} | "
                f"{leg.get('last_fired')} | {leg.get('weeks_since_last_fired')} |"
            )
    for payload, label, horizon in ((squeeze, "SQUEEZE", "12w"), (liq, "LIQUIDITY EXIT", "4w")):
        splits = payload.get("seam_split") or []
        if not splits:
            continue
        lines += [
            "",
            f"## {label} — pre/post 2023-05-02 stability (standing test, {horizon})",
            "",
            "The series no longer has a unit seam at this date, so this is a stability test, not a data "
            "check: a cell whose result lives entirely on one side of it has not been shown to work.",
            "",
            "| condition | pre n_ep | pre mean_ex % | post n_ep | post mean_ex % | both sides | same sign | survives |",
            "|-----------|---------:|--------------:|----------:|---------------:|:----------:|:---------:|:--------:|",
        ]
        for s in splits:
            pre, post = s.get("pre", {}), s.get("post", {})
            lines.append(
                f"| `{s.get('condition')}` | {pre.get('n_episodes', 0)} | {pre.get('mean_excess', '—')} | "
                f"{post.get('n_episodes', 0)} | {post.get('mean_excess', '—')} | "
                f"{'yes' if s.get('fires_both_sides') else 'NO'} | "
                f"{'yes' if s.get('consistent_sign') else 'NO'} | "
                f"{'yes' if s.get('survives_split') else '**NO**'} |"
            )
        dupes = payload.get("duplicate_cells") or []
        if dupes:
            lines += [
                "",
                f"### {label} — cells that are not independent",
                "",
                "These cells fire on exactly the same episodes. They corroborate nothing; they are one "
                "result printed several times.",
                "",
            ]
            for d in dupes[:8]:
                lines.append(
                    f"- **{len(d['conditions'])} cells, {d['n_episodes']} shared episodes:** "
                    + ", ".join(f"`{c}`" for c in d["conditions"])
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
    robustness = run_robustness_checks(
        ctx, run_bootstrap=run_bootstrap, specs=robustness_specs_for_grid(squeeze)
    )
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
