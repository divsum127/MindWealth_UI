"""Shared metrics for regime v2 experiments."""

from __future__ import annotations

from typing import Any

import numpy as np


HORIZONS = ["spx_1w", "spx_2w", "spx_1m", "spx_3m", "spx_6m", "spx_9m", "spx_12m"]


def hit_rate(returns: list[float], bullish: bool = True) -> float | None:
    if not returns:
        return None
    if bullish:
        return sum(1 for r in returns if r > 0) / len(returns)
    return sum(1 for r in returns if r < 0) / len(returns)


def summarize_returns(returns: list[float], bullish: bool = True) -> dict[str, Any]:
    clean = [r for r in returns if r is not None and not (isinstance(r, float) and np.isnan(r))]
    if not clean:
        return {"n": 0, "hit_rate": None, "avg": None, "median": None, "worst": None}
    return {
        "n": len(clean),
        "hit_rate": hit_rate(clean, bullish=bullish),
        "avg": float(np.mean(clean)),
        "median": float(np.median(clean)),
        "worst": float(min(clean)) if bullish else float(max(clean)),
    }


BENCHMARK_PCT = {
    "spx_1w": 0.5,
    "spx_2w": 1.0,
    "spx_1m": 1.25,
    "spx_3m": 2.5,
    "spx_6m": 5.0,
    "spx_9m": 7.5,
    "spx_12m": 10.0,
}


def probability_weighted_summary(
    returns: list[float],
    bullish: bool = True,
    benchmark_pct: float | None = None,
    horizon: str = "spx_3m",
) -> dict[str, Any]:
    """Hit rate, avg win/loss, PW expected return, benchmark, excess (Rohit v2 format)."""
    clean = [float(r) for r in returns if r is not None and r == r]
    if not clean:
        return {
            "n": 0,
            "hit_rate": None,
            "avg_win": None,
            "avg_loss": None,
            "pw_expected": None,
            "benchmark_pct": benchmark_pct or BENCHMARK_PCT.get(horizon, 2.5),
            "excess_pct": None,
        }
    wins = [r for r in clean if (r > 0 if bullish else r < 0)]
    losses = [r for r in clean if (r <= 0 if bullish else r >= 0)]
    hr = len(wins) / len(clean)
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    pw = hr * avg_win + (1 - hr) * avg_loss
    bench = benchmark_pct if benchmark_pct is not None else BENCHMARK_PCT.get(horizon, 2.5)
    return {
        "n": len(clean),
        "hit_rate": hr,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "pw_expected": pw,
        "benchmark_pct": bench,
        "excess_pct": pw - bench,
        **summarize_returns(clean, bullish=bullish),
    }


def evidence_tag(n: int, mechanism: bool = False) -> str:
    if mechanism:
        return "MECHANISM+ANALOG"
    if n >= 5:
        return "STATISTICAL"
    return "INSUFFICIENT"


def slice_by_regime(
    rows: list[dict[str, Any]],
    regime_key: str,
    horizon: str = "spx_3m",
    bullish: bool = True,
) -> dict[str, dict[str, Any]]:
    """Group rows with 'returns' dict and 'regime' dict by regime dimension value."""
    buckets: dict[str, list[float]] = {}
    for row in rows:
        reg = row.get("regime") or {}
        val = str(reg.get(regime_key, "UNKNOWN"))
        ret = (row.get("returns") or {}).get(horizon)
        if ret is None:
            continue
        buckets.setdefault(val, []).append(float(ret))
    return {k: summarize_returns(v, bullish=bullish) for k, v in sorted(buckets.items())}
