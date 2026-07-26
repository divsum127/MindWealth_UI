"""Risk stats derived from monthly NAV / benchmark return series."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Sequence


def monthly_return_pcts(closes: Sequence[float]) -> list[float]:
    return _monthly_return_pcts(closes)


def _monthly_return_pcts(closes: Sequence[float]) -> list[float]:
    if len(closes) < 2:
        return []
    out: list[float] = []
    for prev, cur in zip(closes[:-1], closes[1:]):
        if prev and prev > 0:
            out.append((cur / prev - 1.0) * 100.0)
    return out


def realized_vol_pct(monthly_return_pcts: Sequence[float]) -> float | None:
    if len(monthly_return_pcts) < 2:
        return None
    mean = sum(monthly_return_pcts) / len(monthly_return_pcts)
    var = sum((x - mean) ** 2 for x in monthly_return_pcts) / (len(monthly_return_pcts) - 1)
    return round(math.sqrt(var) * math.sqrt(12), 2)


def beta_sp500(
    portfolio_monthly_pcts: Sequence[float],
    benchmark_monthly_decimals: Sequence[float],
) -> float | None:
    if len(portfolio_monthly_pcts) < 2 or len(benchmark_monthly_decimals) < 2:
        return None
    n = min(len(portfolio_monthly_pcts), len(benchmark_monthly_decimals))
    port = portfolio_monthly_pcts[:n]
    bench = [b * 100.0 for b in benchmark_monthly_decimals[:n]]
    mean_p = sum(port) / n
    mean_b = sum(bench) / n
    cov = sum((p - mean_p) * (b - mean_b) for p, b in zip(port, bench)) / (n - 1)
    var_b = sum((b - mean_b) ** 2 for b in bench) / (n - 1)
    if var_b <= 0:
        return None
    return round(cov / var_b, 2)


def best_worst_month(monthly_return_pcts: Sequence[float]) -> tuple[float | None, float | None]:
    if not monthly_return_pcts:
        return None, None
    return round(max(monthly_return_pcts), 2), round(min(monthly_return_pcts), 2)


def _nav_points_from_series(
    dates: Sequence[str],
    closes: Sequence[float],
    *,
    date_resolver: Callable[[str], str] | None = None,
) -> list[dict[str, float | str]]:
    """Build HANDOFF nav points with drawdown and high-water mark."""
    if not closes:
        return []
    hwm = closes[0]
    points: list[dict[str, float | str]] = []
    for label, value in zip(dates, closes):
        iso = date_resolver(label) if date_resolver else str(label)
        hwm = max(hwm, value)
        dd = ((value / hwm) - 1.0) * 100.0 if hwm > 0 else 0.0
        points.append({
            "date": iso,
            "value": round(value, 2),
            "drawdown_pct": round(dd, 2),
            "high_water_mark": round(hwm, 2),
        })
    return points


def build_nav_points(
    month_labels: Sequence[str],
    closes: Sequence[float],
) -> list[dict[str, float | str]]:
    """Build monthly HANDOFF nav points (month labels like Jan-24 → month-end ISO)."""
    return _nav_points_from_series(month_labels, closes, date_resolver=_month_end_iso)


def build_daily_nav_points(
    iso_dates: Sequence[str],
    closes: Sequence[float],
) -> list[dict[str, float | str]]:
    """Build daily HANDOFF nav points (dates already YYYY-MM-DD)."""
    return _nav_points_from_series(iso_dates, closes)


def _month_end_iso(mmm_yy: str) -> str:
    """Convert workbook label 'Jan-24' to month-end ISO date (last day approx)."""
    from datetime import datetime
    from calendar import monthrange

    text = (mmm_yy or "").strip()
    try:
        dt = datetime.strptime(text, "%b-%y")
    except ValueError:
        return text
    last = monthrange(dt.year, dt.month)[1]
    return f"{dt.year:04d}-{dt.month:02d}-{last:02d}"
