"""Test 21: Staleness decay — predictive power by post-print age bucket.

For each forward-filled SSI input, split historical observations by calendar days since
last print (age 1–5 post-print) and measure SPX forward-return predictability at 1/2/4/8 weeks.

No weight penalty applied — raw signal levels only, so results are not confounded by the
0.8 discount factor used in live scoring.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.data.cftc_pull import (
    fetch_cftc_asset_manager_net,
    fetch_cftc_fast_money_net,
)
from src.sentiment_superindex.data.margin_debt_pull import fetch_margin_debt
from src.sentiment_superindex.analysis.dbmf_beta_study import _ols_regression
from src.sentiment_superindex.analysis.forward_metrics import load_spx
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet
from src.sentiment_superindex.config import SSI_INPUT_CADENCE
from src.sentiment_superindex.data.aaii_pull import fetch_aaii_spread
from src.sentiment_superindex.data.cnn_fear_greed import load_cnn_series
from src.sentiment_superindex.data.naaim_pull import fetch_naaim_exposure
from src.sentiment_superindex.data.staleness import calendar_stale_days


def _max_stale() -> dict[str, int]:
    """Calibrated caps, read from SSI_CONFIG.yaml so the report can never contradict the code."""
    from src.sentiment_superindex.config import staleness_policy

    return staleness_policy()[0]



HORIZONS: dict[str, int] = {"1w": 5, "2w": 10, "4w": 20, "8w": 40}
AGE_BUCKETS = (1, 2, 3, 4, 5)

SIGNAL_LOADERS: dict[str, Any] = {
    "aaii_spread": fetch_aaii_spread,
    "naaim_exposure": fetch_naaim_exposure,
    "cnn_fg": load_cnn_series,
    "cftc_fm_net": fetch_cftc_fast_money_net,
    "cftc_rm_net": fetch_cftc_asset_manager_net,
}


def _load_margin_debt() -> pd.Series:
    return fetch_margin_debt()


def _print_dates(series: pd.Series) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(series.dropna().index.unique()).sort_values()


def _trade_date_on_or_after(dt: pd.Timestamp, spx_index: pd.DatetimeIndex) -> pd.Timestamp | None:
    future = spx_index[spx_index >= dt.normalize()]
    if future.empty:
        return None
    return pd.Timestamp(future[0])


def _directional_hit_rate(signal: pd.Series, fwd: pd.Series) -> float | None:
    """% of observations where signal direction matches forward return direction."""
    aligned = pd.DataFrame({"signal": signal, "fwd": fwd}).dropna()
    if len(aligned) < 30:
        return None
    try:
        from scipy.stats import linregress

        slope, _, _, _, _ = linregress(aligned["signal"], aligned["fwd"])
    except ImportError:
        x = aligned["signal"].values
        y = aligned["fwd"].values
        x_mean = x.mean()
        ss_xy = ((x - x_mean) * (y - y.mean())).sum()
        ss_xx = ((x - x_mean) ** 2).sum()
        slope = ss_xy / ss_xx if ss_xx > 1e-12 else 0.0
    if abs(slope) < 1e-12:
        return None
    pred = np.sign(slope * (aligned["signal"] - aligned["signal"].mean()))
    actual = np.sign(aligned["fwd"])
    return round(float((pred == actual).mean() * 100), 2)


def _build_age_panel(
    series: pd.Series,
    spx: pd.Series,
    *,
    start: str,
) -> pd.DataFrame:
    """Calendar-day ages 1–5 post-print; SPX forward returns from first session on/after each day."""
    series = series.sort_index().dropna()
    spx = spx.sort_index()
    if series.empty or spx.empty:
        return pd.DataFrame()

    prints = _print_dates(series)
    start_ts = max(pd.Timestamp(start), prints.min(), spx.index.min())
    end_ts = min(spx.index.max(), pd.Timestamp.now().normalize())
    cal = pd.date_range(start_ts, end_ts, freq="D")

    fwd: dict[str, pd.Series] = {}
    for label, days in HORIZONS.items():
        fwd[label] = spx.pct_change(days).shift(-days) * 100

    rows: list[dict[str, Any]] = []
    for dt in cal:
        prior = prints[prints <= dt]
        if prior.empty:
            continue
        last_ts = prior[-1]
        stale = calendar_stale_days(pd.Timestamp(dt), pd.Timestamp(last_ts))
        if stale not in AGE_BUCKETS:
            continue
        trade_dt = _trade_date_on_or_after(pd.Timestamp(dt), spx.index)
        if trade_dt is None:
            continue
        row: dict[str, Any] = {
            "date": pd.Timestamp(dt),
            "trade_date": trade_dt,
            "value": float(series.loc[last_ts]),
            "stale_days": stale,
            "print_date": pd.Timestamp(last_ts),
        }
        for label in HORIZONS:
            val = fwd[label].get(trade_dt) if trade_dt in fwd[label].index else None
            row[f"ret_{label}"] = float(val) if val is not None and pd.notna(val) else None
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("date").sort_index()


def _analyze_signal(
    series_key: str,
    series: pd.Series,
    spx: pd.Series,
    *,
    start: str,
) -> dict[str, Any]:
    panel = _build_age_panel(series, spx, start=start)
    cadence = SSI_INPUT_CADENCE.get(series_key, "weekly")
    age_results: list[dict[str, Any]] = []

    if panel.empty:
        return {
            "series_key": series_key,
            "cadence": cadence,
            "n_obs_total": 0,
            "age_buckets": age_results,
            "note": "no observations in age buckets 1-5",
        }

    for age in AGE_BUCKETS:
        subset = panel[panel["stale_days"] == age]
        horizon_metrics: dict[str, Any] = {}
        for label in HORIZONS:
            ret_col = f"ret_{label}"
            ols = _ols_regression(subset["value"], subset[ret_col])
            hit = _directional_hit_rate(subset["value"], subset[ret_col])
            horizon_metrics[label] = {
                "n": ols["n"],
                "r2": ols["r2"],
                "p_value": ols["p_value"],
                "slope": ols["slope"],
                "hit_rate_pct": hit,
            }
        age_results.append(
            {
                "age_post_print": age,
                "n_obs": len(subset),
                "horizons": horizon_metrics,
            }
        )

    return {
        "series_key": series_key,
        "cadence": cadence,
        "n_obs_total": len(panel),
        "age_buckets": age_results,
    }


def _penalty_recommendation(age_results: list[dict[str, Any]]) -> str:
    """Compare youngest vs oldest age bucket with adequate sample at 4w horizon."""
    by_age = {r["age_post_print"]: r for r in age_results}
    d1 = by_age.get(1, {}).get("horizons", {}).get("4w", {})
    r1 = d1.get("r2")

    oldest_age = None
    d_old: dict[str, Any] = {}
    for age in sorted(AGE_BUCKETS, reverse=True):
        h = by_age.get(age, {}).get("horizons", {}).get("4w", {})
        if (h.get("n") or 0) >= 100 and h.get("r2") is not None:
            oldest_age = age
            d_old = h
            break

    r_old = d_old.get("r2")
    if r1 is None or r_old is None or oldest_age is None:
        return "insufficient data"
    if r1 <= 1e-9:
        return "no predictive power at day-1 (R²≈0) — penalty not meaningful"
    ratio = r_old / r1
    if ratio >= 0.9:
        return f"no penalty warranted (day-{oldest_age} R² ≥ 90% of day-1)"
    return (
        f"decay detected — day-{oldest_age}/day-1 R² ratio={ratio:.2f} at 4w "
        f"(suggest penalty ≈ {ratio:.2f}, not global 0.8)"
    )


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    spx = load_spx(start)
    signals: dict[str, pd.Series] = {}
    for key, loader in SIGNAL_LOADERS.items():
        try:
            signals[key] = loader()
        except Exception as exc:
            signals[key] = pd.Series(dtype=float, name=key)
            signals[key].attrs["load_error"] = str(exc)

    try:
        signals["margin_debt"] = _load_margin_debt()
    except Exception as exc:
        signals["margin_debt"] = pd.Series(dtype=float, name="margin_debt")
        signals["margin_debt"].attrs["load_error"] = str(exc)

    results: list[dict[str, Any]] = []
    for key, series in signals.items():
        if series.empty:
            note = series.attrs.get("load_error", "empty series")
            results.append(
                {
                    "series_key": key,
                    "cadence": SSI_INPUT_CADENCE.get(key, "weekly"),
                    "n_obs_total": 0,
                    "age_buckets": [],
                    "note": note,
                }
            )
            continue
        out = _analyze_signal(key, series, spx, start=start)
        if key == "cnn_fg" and out.get("n_obs_total", 0) == 0:
            out["note"] = (
                "CNN cache has contiguous business-day prints — no age 1–5 carry-forward "
                "on trading days in history; daily cap (3d) applies to live fetch gaps only"
            )
        out["penalty_recommendation"] = _penalty_recommendation(out.get("age_buckets", []))
        results.append(out)

    payload = {
        "test_id": "21_staleness_decay",
        "start": start,
        "max_stale_days_calibrated": _max_stale(),
        "method": (
            "Calendar-day age since last print; SPX forward returns from first session "
            "on/after each day; no stale weight penalty applied"
        ),
        "horizons_trading_days": HORIZONS,
        "age_buckets_calendar_days": list(AGE_BUCKETS),
        "signals": results,
    }
    save_artifact("21_staleness_decay", payload)

    md = "# Test 21: Staleness decay by post-print age\n\n"
    md += (
        "Measures whether forward-filled signal values predict SPX returns at ages 1–5 "
        "calendar days post-print. **No 0.8 weight penalty applied.**\n\n"
    )
    md += (
        f"Start: {start} | Horizons: {', '.join(HORIZONS)} trading days | "
        f"MAX_STALE_DAYS calibrated: "
        f"weekly={_max_stale()['weekly']}, daily={_max_stale()['daily']}, "
        f"monthly={_max_stale()['monthly']}\n\n"
    )

    for sig in results:
        md += f"## {sig['series_key']} ({sig['cadence']}, n={sig.get('n_obs_total', 0)})\n"
        if sig.get("note") and not sig.get("age_buckets"):
            md += f"*{sig['note']}*\n\n"
            continue
        md += f"**Penalty recommendation:** {sig.get('penalty_recommendation', '—')}\n\n"
        if sig.get("note"):
            md += f"*{sig['note']}*\n\n"
        md += "| Age | Horizon | n | R² | p-value | Hit % | Slope |\n"
        md += "|-----|---------|---|-----|---------|-------|-------|\n"
        for bucket in sig.get("age_buckets", []):
            age = bucket["age_post_print"]
            for hz, m in bucket.get("horizons", {}).items():
                md += (
                    f"| {age} | {hz} | {m.get('n', 0)} | {m.get('r2', '—')} | "
                    f"{m.get('p_value', '—')} | {m.get('hit_rate_pct', '—')} | "
                    f"{m.get('slope', '—')} |\n"
                )
        md += "\n"

    write_md_snippet("21_staleness_decay", md)
    return payload
