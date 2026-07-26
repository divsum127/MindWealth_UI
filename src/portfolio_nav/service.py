"""Portfolio NAV history orchestration — nav_engine first, workbook fallback."""

from __future__ import annotations

import logging
import os
from typing import Any

from src.portfolio_nav.engine_provider import engine_available, load_engine_history
from src.portfolio_nav.stats import beta_sp500, best_worst_month, realized_vol_pct
from src.portfolio_nav.types import NavHistoryBundle, NavPoint
from src.portfolio_nav.workbook_provider import load_workbook_history, workbook_available

logger = logging.getLogger(__name__)


class NavHistoryUnavailableError(FileNotFoundError):
    """No NAV history source (engine or workbook) is available."""


def get_nav_history(book: str) -> NavHistoryBundle:
    """Resolve NAV monthly history for a MODEL valuation book."""
    if os.getenv("PORTFOLIO_NAV_FORCE_WORKBOOK", "").lower() in ("1", "true", "yes"):
        if workbook_available():
            return load_workbook_history(book)
        raise NavHistoryUnavailableError("Workbook forced but Ahil xlsx not found")

    try:
        engine_bundle = load_engine_history(book)
        if engine_bundle is not None:
            return engine_bundle
    except Exception as exc:
        logger.warning("nav_engine failed (%s); falling back to workbook", exc)

    if workbook_available():
        return load_workbook_history(book)
    raise NavHistoryUnavailableError(
        "NAV history unavailable: nav_engine failed and workbooks missing under ahil_analysis/"
    )


def nav_history_status() -> dict[str, Any]:
    return {
        "engine_available": engine_available(),
        "workbook_available": workbook_available(),
        "active_source": "nav_engine" if engine_available() else ("workbook" if workbook_available() else None),
    }


def _points_to_api(points: list[NavPoint]) -> list[dict[str, Any]]:
    return [
        {
            "date": p.date,
            "value": p.value,
            "drawdown_pct": p.drawdown_pct,
            "high_water_mark": p.high_water_mark,
        }
        for p in points
    ]


def _attribution_to_api(bundle: NavHistoryBundle) -> list[dict[str, Any]]:
    return [
        {
            "id": a.id,
            "label": a.label,
            "return_pct": a.return_pct,
            "description": a.description,
        }
        for a in bundle.attribution
    ]


def _monthly_returns_to_api(bundle: NavHistoryBundle) -> list[dict[str, Any]]:
    return [{"month": m.month, "return_pct": m.return_pct} for m in bundle.monthly_returns]


def risk_metrics_from_bundle(bundle: NavHistoryBundle) -> dict[str, float | None]:
    closes = [p.value for p in bundle.mtm]
    monthly_pcts = bundle.monthly_returns
    port_pcts = [m.return_pct for m in monthly_pcts]
    if not port_pcts and len(closes) > 1:
        port_pcts = [(closes[i] / closes[i - 1] - 1.0) * 100.0 for i in range(1, len(closes))]

    bench_decimals: list[float] = []
    if len(bundle.benchmark) == len(closes) and len(closes) > 1:
        bench_decimals = [0.0]
        for i in range(1, len(bundle.benchmark)):
            prev, cur = bundle.benchmark[i - 1].value, bundle.benchmark[i].value
            bench_decimals.append((cur / prev - 1.0) if prev > 0 else 0.0)

    best, worst = best_worst_month(port_pcts)
    return {
        "realized_vol_pct": realized_vol_pct(port_pcts),
        "beta_sp500": beta_sp500(port_pcts, bench_decimals) if bench_decimals else None,
        "best_month_pct": best,
        "worst_month_pct": worst,
        "since_go_live_pct": bundle.since_go_live_pct,
    }


def serialize_history(bundle: NavHistoryBundle) -> dict[str, Any]:
    """HANDOFF-shaped history block for /portfolio/nav merge."""
    risk = risk_metrics_from_bundle(bundle)
    return {
        "nav": bundle.latest_nav,
        "since_go_live_pct": risk["since_go_live_pct"],
        "position_limit": bundle.position_limit,
        "realized_vol_pct": risk["realized_vol_pct"],
        "beta_sp500": risk["beta_sp500"],
        "best_month_pct": risk["best_month_pct"],
        "worst_month_pct": risk["worst_month_pct"],
        "mtm": _points_to_api(bundle.mtm),
        "closed": _points_to_api(bundle.closed),
        "mtm_daily": _points_to_api(bundle.mtm_daily),
        "closed_daily": _points_to_api(bundle.closed_daily),
        "benchmark": _points_to_api(bundle.benchmark),
        "monthly_returns": _monthly_returns_to_api(bundle),
        "attribution": _attribution_to_api(bundle),
        "nav_history_note": bundle.nav_history_note,
        "nav_series_source": bundle.source,
        "nav_series_metadata": {
            **bundle.metadata,
            "mtm_daily_point_count": len(bundle.mtm_daily),
            "mtm_monthly_point_count": len(bundle.mtm),
        },
    }
