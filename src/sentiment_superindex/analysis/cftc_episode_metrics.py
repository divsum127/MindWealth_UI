"""Episode-level CFTC pattern metrics (Rohit Aug 2026 re-run spec)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine.forward_returns import _nyse_sessions, forward_return_pct
from src.macro_intelligence.engine.percentiles import percentile_rank
from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons

# Rohit: keep 4/8/12w from prior run; add 6m/12m
DEFAULT_HORIZONS: dict[str, int] = {
    "4w": 20,
    "8w": 40,
    "12w": 60,
    "6m": 126,
    "12m": 252,
}


# Below this many episodes per offset, "stable across offsets" is arithmetic, not evidence.
MIN_OFFSET_EPISODES = 8


def weekly_pctile_series(
    net: pd.Series,
    weeks: int = 156,
    *,
    min_obs: int | None = None,
) -> pd.Series:
    """Rolling percentile rank, published only once the window is genuinely full.

    ``min_obs`` used to be a hard 20, so the series began ~136 weeks before a 156-week window
    could exist and every GFC-era rank was computed on a partial window while being labelled a
    3-year percentile (Rohit, 24 Aug 2026: "set analysis_start to 2009-06-02, not the
    20-observation date"). Callers that genuinely want the ramp-up can still ask for it.
    """
    required = weeks if min_obs is None else int(min_obs)
    out: list[tuple[pd.Timestamp, float]] = []
    for dt in net.index:
        window = net.loc[:dt].dropna().tail(weeks)
        if len(window) < required:
            continue
        out.append((dt, percentile_rank(float(net.loc[dt]), window)))
    return pd.Series(dict(out)).sort_index()


def collapse_episodes(dates: pd.DatetimeIndex | list[pd.Timestamp]) -> list[pd.Timestamp]:
    """Consecutive qualifying weeks → one episode dated at first fire."""
    if len(dates) == 0:
        return []
    ordered = sorted(pd.Timestamp(d) for d in dates)
    episodes: list[pd.Timestamp] = [ordered[0]]
    prev = ordered[0]
    for dt in ordered[1:]:
        if (dt - prev).days > 10:
            episodes.append(dt)
        prev = dt
    return episodes


def fm_fixed_distribution_cuts(fm: pd.Series) -> dict[str, float]:
    arr = fm.dropna().values.astype(float)
    if len(arr) < 20:
        return {}
    return {
        "p2_5": float(np.percentile(arr, 2.5)),
        "p5": float(np.percentile(arr, 5)),
        "p10": float(np.percentile(arr, 10)),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "median": float(np.median(arr)),
        "n": int(len(arr)),
    }


def build_market_benchmark(
    spx: pd.Series,
    weekly_index: pd.DatetimeIndex,
    horizons: dict[str, int] | None = None,
    *,
    sessions: pd.DatetimeIndex | None = None,
) -> dict[str, float | None]:
    """Average SPX forward return across all weeks in sample (centering constant)."""
    horizons = horizons or DEFAULT_HORIZONS
    sessions = _nyse_sessions() if sessions is None else sessions
    rows = returns_at_horizons(spx, weekly_index, horizons=horizons)
    bench: dict[str, float | None] = {}
    for label in horizons:
        key = f"ret_{label}"
        vals = [r[key] for r in rows if r.get(key) is not None]
        bench[label] = float(np.mean(vals)) if vals else None
    return bench


def _split_pos_neg(vals: list[float]) -> dict[str, float | None]:
    if not vals:
        return {"avg_positive": None, "median_positive": None, "avg_negative": None, "median_negative": None}
    pos = [v for v in vals if v > 0]
    neg = [v for v in vals if v < 0]
    return {
        "avg_positive": round(float(np.mean(pos)), 4) if pos else None,
        "median_positive": round(float(np.median(pos)), 4) if pos else None,
        "avg_negative": round(float(np.mean(neg)), 4) if neg else None,
        "median_negative": round(float(np.median(neg)), 4) if neg else None,
    }


def summarize_episode_horizon(
    returns: list[float],
    *,
    benchmark: float | None,
    long_side: bool = True,
    horizon_days: int | None = None,
) -> dict[str, Any]:
    if not returns:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "mean_median_gap": None,
            "hit_pct": None,
            "best": None,
            "worst": None,
            "sharpe": None,
            "mean_excess": None,
            "median_excess": None,
            "hit_excess_pct": None,
            **_split_pos_neg([]),
        }
    arr = np.array(returns, dtype=float)
    mean = float(arr.mean())
    median = float(np.median(arr))
    if long_side:
        hits = int((arr > 0).sum())
        best = float(arr.max())
        worst = float(arr.min())
    else:
        hits = int((arr < 0).sum())
        best = float(arr.min())
        worst = float(arr.max())
    excess_arr = arr - benchmark if benchmark is not None else None
    std = float(arr.std())
    sharpe = None
    if horizon_days and std > 1e-9:
        sharpe = round(float(mean / std * np.sqrt(252 / horizon_days)), 4)
    if excess_arr is not None:
        if long_side:
            excess_hits = int((excess_arr > 0).sum())
        else:
            excess_hits = int((excess_arr < 0).sum())
    else:
        excess_hits = None
    return {
        "n": len(arr),
        "mean": round(mean, 4),
        "median": round(median, 4),
        "mean_median_gap": round(mean - median, 4),
        "hit_pct": round(hits / len(arr) * 100, 2),
        "best": round(best, 4),
        "worst": round(worst, 4),
        "sharpe": sharpe,
        "mean_excess": round(float(excess_arr.mean()), 4) if excess_arr is not None else None,
        "median_excess": round(float(np.median(excess_arr)), 4) if excess_arr is not None else None,
        "hit_excess_pct": round(excess_hits / len(excess_arr) * 100, 2) if excess_hits is not None else None,
        **_split_pos_neg(arr.tolist()),
    }


def episode_return_table(
    spx: pd.Series,
    episode_dates: list[pd.Timestamp],
    horizons: dict[str, int] | None = None,
    *,
    sessions: pd.DatetimeIndex | None = None,
    benchmark: dict[str, float | None] | None = None,
) -> list[dict[str, Any]]:
    horizons = horizons or DEFAULT_HORIZONS
    sessions = _nyse_sessions() if sessions is None else sessions
    benchmark = benchmark or {}
    rows: list[dict[str, Any]] = []
    for dt in episode_dates:
        row: dict[str, Any] = {"date": str(pd.Timestamp(dt).date())}
        for label, days in horizons.items():
            ret = forward_return_pct(spx, dt, days, sessions=sessions)
            row[f"ret_{label}"] = round(ret, 4) if ret is not None else None
            b = benchmark.get(label)
            row[f"excess_{label}"] = round(ret - b, 4) if ret is not None and b is not None else None
        rows.append(row)
    return rows


def analyze_par_row(
    weekly_index: pd.DatetimeIndex,
    spx: pd.Series,
    *,
    benchmark: dict[str, float | None],
    horizons: dict[str, int] | None = None,
    sessions: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """Unconditional baseline: every week in sample, no episode collapse."""
    return analyze_cell(
        weekly_index,
        spx,
        benchmark=benchmark,
        horizons=horizons,
        sessions=sessions,
        long_side=True,
        collapse=False,
    )


def analyze_cell(
    week_dates: pd.DatetimeIndex,
    spx: pd.Series,
    *,
    benchmark: dict[str, float | None],
    horizons: dict[str, int] | None = None,
    sessions: pd.DatetimeIndex | None = None,
    long_side: bool = True,
    top_episodes: int = 9,
    collapse: bool = True,
) -> dict[str, Any]:
    horizons = horizons or DEFAULT_HORIZONS
    sessions = _nyse_sessions() if sessions is None else sessions
    if collapse:
        episodes = collapse_episodes(week_dates)
    else:
        episodes = sorted(pd.Timestamp(d) for d in week_dates)
    ep_table = episode_return_table(spx, episodes, horizons, sessions=sessions, benchmark=benchmark)
    metrics: dict[str, Any] = {}
    for label in horizons:
        key = f"ret_{label}"
        vals = [r[key] for r in ep_table if r.get(key) is not None]
        metrics[label] = summarize_episode_horizon(
            vals,
            benchmark=benchmark.get(label),
            long_side=long_side,
            horizon_days=horizons[label],
        )
    # Rank episodes by 12w return (or 8w if 12w sparse) for dated list
    sort_key = "ret_12w" if any(r.get("ret_12w") is not None for r in ep_table) else "ret_8w"
    ranked = sorted(
        [r for r in ep_table if r.get(sort_key) is not None],
        key=lambda r: r[sort_key],
        reverse=long_side,
    )
    return {
        "n_weeks": len(week_dates),
        "n_episodes": len(episodes),
        "metrics": metrics,
        "episodes": ranked[:top_episodes],
        "all_episodes": ep_table,
    }


def subsample_stability_weekly(
    qualifying_dates: pd.DatetimeIndex,
    weekly_calendar: pd.DatetimeIndex,
    spx: pd.Series,
    *,
    benchmark: dict[str, float | None],
    horizon_label: str = "12w",
    horizons: dict[str, int] | None = None,
    stride: int = 12,
    long_side: bool = True,
    sessions: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """Non-overlapping weekly subsample stability (Rohit primary robustness test).

    Partition the analysis calendar into ``stride`` non-overlapping subsamples
    (every ``stride``-th week starting at offset 0..stride-1). At each offset,
    re-run episode collapse + forward-return metrics on qualifying weeks only.
    """
    horizons = horizons or DEFAULT_HORIZONS
    if horizon_label not in horizons:
        return {}
    sessions = _nyse_sessions() if sessions is None else sessions
    qual_set = set(pd.Timestamp(d) for d in qualifying_dates)
    full = analyze_cell(
        qualifying_dates,
        spx,
        benchmark=benchmark,
        horizons=horizons,
        sessions=sessions,
        long_side=long_side,
    )
    full_m = full.get("metrics", {}).get(horizon_label, {})
    offset_rows: list[dict[str, Any]] = []
    for off in range(stride):
        sub_cal = weekly_calendar[off::stride]
        sub_qual = pd.DatetimeIndex([d for d in sub_cal if d in qual_set])
        if len(sub_qual) == 0:
            offset_rows.append(
                {
                    "offset": off,
                    "n_weeks": 0,
                    "n_episodes": 0,
                    "mean": None,
                    "median": None,
                    "mean_excess": None,
                    "hit_pct": None,
                    "hit_excess_pct": None,
                }
            )
            continue
        cell = analyze_cell(
            sub_qual,
            spx,
            benchmark=benchmark,
            horizons=horizons,
            sessions=sessions,
            long_side=long_side,
        )
        m = cell.get("metrics", {}).get(horizon_label, {})
        offset_rows.append(
            {
                "offset": off,
                "n_weeks": int(cell.get("n_weeks", 0)),
                "n_episodes": int(cell.get("n_episodes", 0)),
                "mean": m.get("mean"),
                "median": m.get("median"),
                "mean_excess": m.get("mean_excess"),
                "hit_pct": m.get("hit_pct"),
                "hit_excess_pct": m.get("hit_excess_pct"),
            }
        )
    excess_vals = [r["mean_excess"] for r in offset_rows if r.get("mean_excess") is not None]
    spread = float(np.max(excess_vals) - np.min(excess_vals)) if len(excess_vals) >= 2 else None
    full_excess = full_m.get("mean_excess")
    n_positive = sum(1 for v in excess_vals if v is not None and v > 0)
    n_with_data = len(excess_vals)
    return {
        "method": "weekly_calendar_stride",
        "stride": stride,
        "horizon": horizon_label,
        "full": {
            "n_weeks": full.get("n_weeks"),
            "n_episodes": full.get("n_episodes"),
            "mean": full_m.get("mean"),
            "median": full_m.get("median"),
            "mean_excess": full_excess,
            "hit_pct": full_m.get("hit_pct"),
            "hit_excess_pct": full_m.get("hit_excess_pct"),
        },
        "offsets": offset_rows,
        "offset_excess_spread": round(spread, 4) if spread is not None else None,
        "offsets_positive_excess": n_positive,
        "offsets_with_data": n_with_data,
        "median_episodes_per_offset": int(np.median([r["n_episodes"] for r in offset_rows])) if offset_rows else 0,
        "min_episodes_per_offset": int(np.min([r["n_episodes"] for r in offset_rows])) if offset_rows else 0,
        # Rohit: "the offsets carry 2-7 episodes each, so 'stable across offsets' isn't meaningful
        # at that size". Agreeing sign across twelve two-episode subsamples is not evidence, so the
        # verdict is withheld below a floor rather than reported as a pass.
        "meaningful_offset_size": bool(
            offset_rows and float(np.median([r["n_episodes"] for r in offset_rows])) >= MIN_OFFSET_EPISODES
        ),
        "stable_across_offsets": (
            n_with_data >= 8
            and n_positive >= max(8, int(0.67 * n_with_data))
            and bool(offset_rows)
            and float(np.median([r["n_episodes"] for r in offset_rows])) >= MIN_OFFSET_EPISODES
        ),
    }


def subsample_stability(
    week_dates: pd.DatetimeIndex,
    spx: pd.Series,
    *,
    benchmark: dict[str, float | None],
    weekly_calendar: pd.DatetimeIndex | None = None,
    horizon_label: str = "12w",
    horizons: dict[str, int] | None = None,
    offsets: int = 12,
    long_side: bool = True,
) -> dict[str, Any]:
    """Backward-compatible wrapper — delegates to weekly calendar subsampling."""
    if weekly_calendar is None:
        weekly_calendar = pd.DatetimeIndex(sorted(week_dates))
    return subsample_stability_weekly(
        week_dates,
        weekly_calendar,
        spx,
        benchmark=benchmark,
        horizon_label=horizon_label,
        horizons=horizons,
        stride=offsets,
        long_side=long_side,
    )


def _stationary_bootstrap_indices(length: int, sample_len: int, mean_block: int, rng: np.random.Generator) -> np.ndarray:
    """Politis–Romano stationary bootstrap indices."""
    p = 1.0 / mean_block
    out = np.empty(sample_len, dtype=int)
    t = int(rng.integers(0, length))
    for i in range(sample_len):
        out[i] = t
        if rng.random() < p:
            t = int(rng.integers(0, length))
        else:
            t = (t + 1) % length
    return out


def stationary_block_bootstrap(
    qualifying_dates: pd.DatetimeIndex,
    weekly_calendar: pd.DatetimeIndex,
    spx: pd.Series,
    *,
    benchmark: dict[str, float | None],
    horizon_label: str = "12w",
    horizons: dict[str, int] | None = None,
    block_weeks: int = 12,
    n_draws: int = 10_000,
    long_side: bool = True,
    sessions: pd.DatetimeIndex | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Stationary block bootstrap (Politis–Romano) on weekly calendar rows."""
    horizons = horizons or DEFAULT_HORIZONS
    if horizon_label not in horizons:
        return {}
    sessions = _nyse_sessions() if sessions is None else sessions
    qual_set = set(pd.Timestamp(d) for d in qualifying_dates)
    weekly_rows = returns_at_horizons(
        spx,
        weekly_calendar,
        horizons=horizons,
    )
    bench = benchmark.get(horizon_label)
    ret_key = f"ret_{horizon_label}"
    exc_key = f"excess_{horizon_label}"
    ordered_dates: list[pd.Timestamp] = []
    for row in weekly_rows:
        dt = pd.Timestamp(row["date"])
        ret = row.get(ret_key)
        row[exc_key] = round(ret - bench, 4) if ret is not None and bench is not None else None
        row["qualifies"] = dt in qual_set
        ordered_dates.append(dt)
    n = len(weekly_rows)
    if n < block_weeks:
        return {"n_draws": 0, "error": "insufficient weekly history"}

    observed = analyze_cell(
        qualifying_dates,
        spx,
        benchmark=benchmark,
        horizons=horizons,
        sessions=sessions,
        long_side=long_side,
    )
    obs_m = observed.get("metrics", {}).get(horizon_label, {})
    obs_mean_excess = obs_m.get("mean_excess")
    ep_table = observed.get("all_episodes", [])

    def _mean_excess_from_resampled(indices: np.ndarray) -> tuple[float | None, list[float]]:
        qual_dates = [
            ordered_dates[i]
            for i in indices
            if weekly_rows[i].get("qualifies") and weekly_rows[i].get(exc_key) is not None
        ]
        if not qual_dates:
            return None, []
        episodes = collapse_episodes(pd.DatetimeIndex(qual_dates))
        ep_excess = []
        date_to_exc = {ordered_dates[i]: weekly_rows[i].get(exc_key) for i in range(n)}
        for ep_dt in episodes:
            val = date_to_exc.get(ep_dt)
            if val is not None:
                ep_excess.append(float(val))
        if not ep_excess:
            return None, []
        return float(np.mean(ep_excess)), ep_excess

    rng = np.random.default_rng(seed)
    boot_means: list[float] = []
    boot_ep_pool: list[float] = []
    for _ in range(n_draws):
        idx = _stationary_bootstrap_indices(n, n, block_weeks, rng)
        mean_exc, ep_vals = _mean_excess_from_resampled(idx)
        if mean_exc is not None:
            boot_means.append(mean_exc)
            boot_ep_pool.extend(ep_vals)

    if not boot_means or obs_mean_excess is None:
        return {
            "n_draws": n_draws,
            "block_weeks": block_weeks,
            "horizon": horizon_label,
            "observed_mean_excess": obs_mean_excess,
            "bootstrap_mean_excess_pctile": None,
            "episode_excess_percentiles": [],
        }

    boot_arr = np.array(boot_means)
    pctile_mean = float((boot_arr <= obs_mean_excess).mean() * 100)
    ep_pctiles: list[dict[str, Any]] = []
    if boot_ep_pool:
        pool = np.array(boot_ep_pool)
        for ep in ep_table:
            val = ep.get(exc_key)
            if val is None:
                continue
            ep_pctiles.append(
                {
                    "date": ep.get("date"),
                    "excess": val,
                    "bootstrap_pctile": round(float((pool <= val).mean() * 100), 2),
                }
            )

    return {
        "method": "stationary_block_bootstrap_politis_romano",
        "n_draws": n_draws,
        "n_successful_draws": len(boot_means),
        "block_weeks": block_weeks,
        "horizon": horizon_label,
        "observed": {
            "n_episodes": observed.get("n_episodes"),
            "mean_excess": obs_mean_excess,
        },
        "bootstrap_mean_excess": {
            "pctile_of_observed": round(pctile_mean, 2),
            "mean": round(float(boot_arr.mean()), 4),
            "median": round(float(np.median(boot_arr)), 4),
            "p5": round(float(np.percentile(boot_arr, 5)), 4),
            "p95": round(float(np.percentile(boot_arr, 95)), 4),
        },
        "episode_excess_percentiles": ep_pctiles,
    }


def _cftc_sample_diagnostics(
    fm: pd.Series,
    rm: pd.Series,
    weeks: int = 156,
    *,
    open_interest: pd.Series | None = None,
) -> dict[str, Any]:
    """The sample window, stated once.

    Rohit counted the sample start given five different ways across our documents
    (2006-01-01, Jun 2009, Sep 2009, 2006-06-13, 2006-10-24). There are only ever two honest
    numbers here -- when the raw weekly prints begin, and when the first *full* rolling window
    closes -- and the analysis starts at the second. ``weekly_pctile_series`` now refuses to rank
    a partial window, so ``analysis_start`` and ``first_full_window`` are the same date by
    construction rather than by coincidence.
    """
    from src.macro_intelligence.data.cftc_pull import detect_unit_break

    fm_pct = weekly_pctile_series(fm, weeks=weeks)
    rm_pct = weekly_pctile_series(rm, weeks=weeks)
    idx = fm_pct.index.intersection(rm_pct.index)
    full_window = None
    for dt in fm.index:
        if len(fm.loc[:dt].dropna().tail(weeks)) >= weeks:
            full_window = dt
            break
    fields = {"fm_net": fm, "rm_net": rm}
    if open_interest is not None and not open_interest.empty:
        fields["open_interest"] = open_interest
    breaks = detect_unit_break(pd.DataFrame(fields).dropna(how="all"))
    return {
        "unit_basis": str(load_config().get("cftc", {}).get("unit_basis", "emini_equivalent")),
        "raw_start": str(fm.index.min().date()) if not fm.empty else None,
        "raw_end": str(fm.index.max().date()) if not fm.empty else None,
        "raw_weeks": int(len(fm)),
        "pctile_window_weeks": int(weeks),
        "first_full_window": str(full_window.date()) if full_window is not None else None,
        "analysis_start": str(idx.min().date()) if not idx.empty else None,
        "analysis_end": str(idx.max().date()) if not idx.empty else None,
        "analysis_weeks": int(len(idx)),
        "unit_breaks": breaks,
    }


def load_analysis_context(
    start: str = "2006-01-01",
    pctile_start: str | None = "2006-01-01",
    cftc_start_year: int = 2006,
) -> dict[str, Any]:
    from src.macro_intelligence.data.cftc_pull import fetch_cftc_asset_manager_net, fetch_cftc_fast_money_net

    from src.macro_intelligence.data.cftc_pull import fetch_cftc_open_interest

    fm = fetch_cftc_fast_money_net(cftc_start_year)
    rm = fetch_cftc_asset_manager_net(cftc_start_year)
    open_interest = fetch_cftc_open_interest(cftc_start_year)
    spx = load_spx("1990-01-01")
    sessions = _nyse_sessions()
    fm_pct = weekly_pctile_series(fm)
    rm_pct = weekly_pctile_series(rm)
    idx = fm_pct.index.intersection(rm_pct.index)
    if pctile_start:
        idx = idx[idx >= pd.Timestamp(pctile_start)]
    idx = idx[idx >= pd.Timestamp(start)]
    benchmark = build_market_benchmark(spx, idx, sessions=sessions)
    fm_dist = fm_fixed_distribution_cuts(fm)
    diag = _cftc_sample_diagnostics(fm, rm, open_interest=open_interest)
    fm_over_oi = (
        (fm / open_interest.reindex(fm.index)).replace([float("inf"), float("-inf")], pd.NA).dropna()
        if not open_interest.empty
        else pd.Series(dtype=float)
    )
    return {
        "fm": fm,
        "rm": rm,
        "open_interest": open_interest,
        # Rohit: "FM / open interest is probably the better construction" -- a share of the market
        # rather than a contract count, so it is comparable across a decade of growth in the venue.
        "fm_over_oi": fm_over_oi.astype(float),
        "spx": spx,
        "sessions": sessions,
        "fm_pct": fm_pct,
        "rm_pct": rm_pct,
        "weekly_index": idx,
        "benchmark": benchmark,
        "fm_distribution": fm_dist,
        "sample_diagnostics": diag,
        "data_note": (
            f"CFTC TFF S&P 500, restated into {diag['unit_basis']} units (component contract lines at "
            "notional weight - E-mini 1.0, big 5.0, micro 0.1 - so CFTC's 2023-05-02 redefinition of the "
            "Consolidated line no longer puts a 5x seam mid-sample); "
            f"raw {diag['raw_start']} to {diag['raw_end']} ({diag['raw_weeks']} weekly prints); "
            f"first full {diag['pctile_window_weeks']}w window {diag['first_full_window']}; "
            f"analysis weeks {diag['analysis_weeks']} ({diag['analysis_start']} to {diag['analysis_end']}); "
            f"unit breaks detected: {diag['unit_breaks'] or 'none'}."
        ),
    }
