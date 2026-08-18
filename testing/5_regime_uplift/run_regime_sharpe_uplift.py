#!/usr/bin/env python3
"""Test 5 — Equal-weight SPY/TLT/GLD/HYG vs 5-dimension regime-scaled overlay."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.db.connection import get_connection

OUT_DIR = Path(__file__).resolve().parent / "output_files"
TICKERS = ["SPY", "TLT", "GLD", "HYG"]
START = "2007-04-11"
RF_ANNUAL = 0.0
MIN_MULT = 0.40
MAX_MULT = 1.00
DEFAULT_DIM_MULT = 0.95

FED_MULT = {
    "TIGHTENING": 0.82,
    "PIVOTING": 0.92,
    "EASING": 1.00,
    "EASY": 1.00,
}
CURVE_MULT = {
    "INVERTED": 0.78,
    "FLAT": 0.90,
    "NORMAL": 1.00,
    "STEEPENING": 0.95,
}
VAL_MULT = {
    "EXTREME_CAPE": 0.85,
    "ELEVATED_CAPE": 0.92,
    "NORMAL": 1.00,
    "CHEAP_CAPE": 1.00,
}
GEO_MULT = {
    "CRISIS": 0.70,
    "ELEVATED_RISK": 0.85,
    "NEUTRAL": 1.00,
}
LIQ_LEVEL_MULT = {
    "TIGHT": 0.80,
    "NEUTRAL": 0.95,
    "EASY": 1.00,
}


def _liquidity_level(liq_v2: str | None) -> str:
    if not liq_v2:
        return "NEUTRAL"
    u = liq_v2.upper()
    if u.startswith("TIGHT"):
        return "TIGHT"
    if u.startswith("EASY"):
        return "EASY"
    return "NEUTRAL"


def dimension_multipliers(reg: dict) -> dict[str, float]:
    fed = str(reg.get("fed_cycle_v2") or "EASY").upper()
    curve = str(reg.get("curve_regime_v2") or "NORMAL").upper()
    val = str(reg.get("val_regime") or "NORMAL").upper()
    geo = str(reg.get("geo_overlay_v2") or reg.get("geo_overlay") or "NEUTRAL").upper()
    liq = _liquidity_level(reg.get("liquidity_v2"))

    return {
        "m_fed": FED_MULT.get(fed, DEFAULT_DIM_MULT),
        "m_curve": CURVE_MULT.get(curve, DEFAULT_DIM_MULT),
        "m_val": VAL_MULT.get(val, DEFAULT_DIM_MULT),
        "m_geo": GEO_MULT.get(geo, DEFAULT_DIM_MULT),
        "m_liq": LIQ_LEVEL_MULT.get(liq, DEFAULT_DIM_MULT),
        "fed_cycle_v2": fed,
        "curve_regime_v2": curve,
        "val_regime": val,
        "geo_overlay_v2": geo,
        "liquidity_v2": str(reg.get("liquidity_v2") or ""),
    }


def combined_mult(parts: dict[str, float]) -> float:
    prod = parts["m_fed"] * parts["m_curve"] * parts["m_val"] * parts["m_geo"] * parts["m_liq"]
    return float(np.clip(prod, MIN_MULT, MAX_MULT))


def load_regime_fridays() -> pd.DataFrame:
    rows: list[dict] = []
    with get_connection() as conn:
        for r in conn.execute(
            "SELECT date, regime_json FROM macro_regime_log_v2 ORDER BY date"
        ).fetchall():
            try:
                reg = json.loads(r["regime_json"] or "{}")
            except json.JSONDecodeError:
                continue
            parts = dimension_multipliers(reg)
            rows.append(
                {
                    "date": pd.Timestamp(r["date"]),
                    **{k: parts[k] for k in parts if k.startswith("m_") or k.endswith("_v2") or k == "val_regime"},
                    "gross_mult": combined_mult(parts),
                }
            )
    return pd.DataFrame(rows).set_index("date").sort_index()


def regime_daily(trading_index: pd.DatetimeIndex, fridays: pd.DataFrame) -> pd.DataFrame:
    # trading_index = Yahoo price trading days (sparse). Unlimited ffill — limit would
    # count trading-day rows, not calendar or business days.
    aligned = fridays.reindex(trading_index, method="ffill")  # limit=None
    return aligned


def load_prices() -> pd.DataFrame:
    series = {}
    for t in TICKERS:
        s = fetch_yahoo_close(t, START)
        if s.empty:
            raise RuntimeError(f"No price data for {t}")
        series[t] = s
    px = pd.DataFrame(series).sort_index()
    px = px.loc[px.index >= pd.Timestamp(START)]
    px = px.dropna(how="any")
    return px


def monthly_equal_weight_returns(prices: pd.DataFrame) -> pd.Series:
    """Daily portfolio returns with monthly rebalance to 25% each."""
    rets = prices.pct_change()
    month_ends = prices.resample("ME").last().index
    weights = pd.Series(0.25, index=TICKERS)
    port_ret = []
    dates = []
    for i, dt in enumerate(prices.index[1:], start=1):
        if dt in month_ends or i == 1:
            weights = pd.Series(0.25, index=TICKERS)
        r_row = rets.loc[dt]
        if r_row.isna().any():
            continue
        port_r = float((weights * r_row).sum())
        port_ret.append(port_r)
        dates.append(dt)
        weights = weights * (1 + r_row)
        weights = weights / weights.sum()
    return pd.Series(port_ret, index=pd.DatetimeIndex(dates), name="ew_return")


def scale_returns(ew: pd.Series, mult: pd.Series) -> pd.Series:
    """Apply lagged gross multiplier; remainder in cash at 0%."""
    # ew.index = trading days. Unlimited ffill before shift(1).
    m = mult.reindex(ew.index).ffill().fillna(1.0).shift(1).fillna(1.0)
    return (m * ew).rename("overlay_return")


def performance_stats(daily_ret: pd.Series) -> dict:
    r = daily_ret.dropna()
    if len(r) < 20:
        return {}
    ann_factor = 252
    mean_d = float(r.mean())
    std_d = float(r.std(ddof=1))
    vol = std_d * np.sqrt(ann_factor) if std_d > 0 else 0.0
    sharpe = (
        (mean_d - RF_ANNUAL / ann_factor) / std_d * np.sqrt(ann_factor) if std_d > 0 else None
    )
    equity = (1 + r).cumprod()
    cagr = float(equity.iloc[-1] ** (ann_factor / len(r)) - 1)
    dd = equity / equity.cummax() - 1
    max_dd = float(dd.min())
    return {
        "n_days": len(r),
        "start": str(r.index.min().date()),
        "end": str(r.index.max().date()),
        "cagr_pct": round(cagr * 100, 2),
        "vol_ann_pct": round(vol * 100, 2),
        "sharpe_ann": round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "total_return_pct": round((equity.iloc[-1] - 1) * 100, 2),
    }


def write_report(
    baseline: dict,
    overlay: dict,
    uplift: dict,
    mult_summary: dict,
    path: Path,
) -> None:
    b_sh = baseline.get("sharpe_ann", "—")
    o_sh = overlay.get("sharpe_ann", "—")
    delta = uplift.get("sharpe_delta")
    delta_s = f"{delta:+.3f}" if delta is not None else "—"
    verdict = (
        "Regime overlay **improves** Sharpe on this sample."
        if delta is not None and delta > 0
        else "Regime overlay **does not improve** Sharpe on this sample — review multiplier table."
    )
    lines = [
        "# Test 5 — Regime Sharpe Uplift Report",
        "",
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Michele headline",
        "",
        f"| Strategy | Sharpe | CAGR | Vol | Max DD |",
        f"|----------|--------|------|-----|--------|",
        f"| Baseline EW (100% gross) | {b_sh} | {baseline.get('cagr_pct')}% | {baseline.get('vol_ann_pct')}% | {baseline.get('max_drawdown_pct')}% |",
        f"| 5-dimension regime overlay | {o_sh} | {overlay.get('cagr_pct')}% | {overlay.get('vol_ann_pct')}% | {overlay.get('max_drawdown_pct')}% |",
        f"| **Sharpe uplift** | **{delta_s}** | | | |",
        "",
        verdict,
        "",
        "## Setup",
        "",
        "- Basket: **SPY, TLT, GLD, HYG** equal-weight, monthly rebalance",
        f"- Sample: **{baseline.get('start')}** → **{baseline.get('end')}** ({baseline.get('n_days')} trading days)",
        "- Overlay: product of 5 dimension multipliers (see `regime_dimension_multipliers_v1_unsigned.md`), lagged 1d, cash at 0%",
        "- EUR=X excluded per spec",
        "",
        "## Regime multiplier distribution",
        "",
        f"- Mean gross mult: **{mult_summary.get('mean_gross_mult')}**",
        f"- Min / max: **{mult_summary.get('min_gross_mult')}** / **{mult_summary.get('max_gross_mult')}**",
        f"- Days at full exposure (mult=1.0): **{mult_summary.get('pct_full_exposure')}%**",
        f"- Days below 0.80: **{mult_summary.get('pct_below_80')}%**",
        "",
        "## Caveats",
        "",
        "1. Multipliers are **v1 economic priors** — not empirically optimised (overfit risk).",
        "2. Regime labels are **weekly v2 shadow** forward-filled to daily.",
        "3. Gross scaling only — does not tilt toward TLT in INVERTED (asset-specific tilts = future work).",
        "4. `regime_backtest.py` (Part D) tested combo hit rates, **not** this portfolio Sharpe test.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = load_prices()
    prices.to_csv(OUT_DIR / "etf_daily_prices.csv")

    fridays = load_regime_fridays()
    regime = regime_daily(prices.index, fridays)
    regime.to_csv(OUT_DIR / "regime_daily.csv")

    ew = monthly_equal_weight_returns(prices)
    overlay = scale_returns(ew, regime["gross_mult"])

    df = pd.DataFrame(
        {
            "ew_return": ew,
            "overlay_return": overlay,
            "gross_mult": regime["gross_mult"].reindex(ew.index).ffill(),
            "gross_mult_lagged": regime["gross_mult"].reindex(ew.index).ffill().shift(1),
        }
    )
    df["equity_baseline"] = (1 + df["ew_return"]).cumprod()
    df["equity_overlay"] = (1 + df["overlay_return"]).cumprod()
    df.to_csv(OUT_DIR / "portfolio_daily_returns.csv")

    baseline_stats = performance_stats(df["ew_return"])
    overlay_stats = performance_stats(df["overlay_return"])
    b_sh = baseline_stats.get("sharpe_ann")
    o_sh = overlay_stats.get("sharpe_ann")
    uplift = {
        "sharpe_delta": round(o_sh - b_sh, 3) if b_sh is not None and o_sh is not None else None,
        "cagr_delta_pp": round(
            overlay_stats.get("cagr_pct", 0) - baseline_stats.get("cagr_pct", 0), 2
        ),
        "max_dd_delta_pp": round(
            overlay_stats.get("max_drawdown_pct", 0) - baseline_stats.get("max_drawdown_pct", 0),
            2,
        ),
    }

    gm = df["gross_mult_lagged"].dropna()
    mult_summary = {
        "mean_gross_mult": round(float(gm.mean()), 3),
        "min_gross_mult": round(float(gm.min()), 3),
        "max_gross_mult": round(float(gm.max()), 3),
        "pct_full_exposure": round(float((gm >= 0.999).mean() * 100), 1),
        "pct_below_80": round(float((gm < 0.80).mean() * 100), 1),
    }

    summary = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "tickers": TICKERS,
        "start": START,
        "baseline": baseline_stats,
        "regime_overlay": overlay_stats,
        "uplift": uplift,
        "mult_summary": mult_summary,
        "multiplier_spec": "testing/5_regime_uplift/regime_dimension_multipliers_v1_unsigned.md",
    }
    (OUT_DIR / "summary_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_report(baseline_stats, overlay_stats, uplift, mult_summary, OUT_DIR / "REPORT.md")

    print("=== Test 5 Regime Sharpe Uplift ===")
    print(f"Sample: {baseline_stats.get('start')} → {baseline_stats.get('end')}")
    print(f"Baseline Sharpe: {b_sh}")
    print(f"Overlay  Sharpe: {o_sh}")
    print(f"Sharpe uplift:   {uplift.get('sharpe_delta')}")
    print(f"Outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
