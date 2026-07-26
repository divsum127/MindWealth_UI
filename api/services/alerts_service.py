"""GET /alerts — aggregate cross-page alert feed (Phase 6).

Pulls from data already computed elsewhere (no new engine) so alerts can never silently drift
from what Holdings/Risk/Sizing show:

  - correlation breaches           → api/services/portfolio_service.py::get_portfolio_risk
  - cross-function exit conflicts  → portfolio_pipeline_service.get_portfolio_risk_report
  - DRIFT (hold time over average) → portfolio_pipeline_service.get_portfolio_holdings
  - negative R:R with no sibling scope covering the asset → same holdings payload
  - recent 1C/A2 evictions         → src/portfolio_nav/book_snapshot_store.read_evictions
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from api.services import portfolio_pipeline_service as pipeline_svc
from api.services import portfolio_service as portfolio_svc
from src.portfolio_nav import book_snapshot_store

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _correlation_alerts(scenario: str) -> list[dict[str, Any]]:
    try:
        risk = portfolio_svc.get_portfolio_risk(scenario=scenario)
    except Exception:
        return []
    alerts: list[dict[str, Any]] = []
    for idx, breach in enumerate(risk.get("breaches") or []):
        labels = breach.get("pair_labels") or []
        pair_text = " / ".join(str(x) for x in labels) if labels else "cluster pair"
        level = str(breach.get("level") or "watch")
        alerts.append({
            "id": f"correlation-{idx}",
            "type": "correlation_breach",
            "severity": "critical" if level == "breach" else "warning",
            "title": f"Correlation breach ({level})",
            "body": breach.get("recommendation") or f"{pair_text} \u03c1={breach.get('rho')}",
            "target_page": "risk",
            "ticker": None,
        })
    return alerts


def _conflict_alerts(book_id: str) -> list[dict[str, Any]]:
    try:
        report = pipeline_svc.get_portfolio_risk_report(book_id)
    except Exception:
        return []
    alerts: list[dict[str, Any]] = []
    for conflict in report.get("cross_function_conflicts") or []:
        if not conflict.get("conflict"):
            continue
        sym = conflict.get("symbol")
        alerts.append({
            "id": f"conflict-{sym}",
            "type": "cross_function_conflict",
            "severity": "warning",
            "title": f"Cross-function exit conflict — {sym}",
            "body": (
                f"{sym}: exit triggered on one function while "
                f"{len(conflict.get('open_positions') or [])} other function(s) remain open."
            ),
            "target_page": "risk",
            "ticker": sym,
        })
    return alerts


def _holdings_alerts(book_id: str, book: str, scenario: str) -> list[dict[str, Any]]:
    try:
        holdings_payload = pipeline_svc.get_portfolio_holdings(book_id, book, scenario=scenario)
    except Exception:
        return []
    alerts: list[dict[str, Any]] = []
    for h in holdings_payload.get("holdings") or []:
        sym = h.get("ticker")
        hold_pct = h.get("hold_time_used_pct")
        if hold_pct is not None and hold_pct > 100:
            alerts.append({
                "id": f"drift-{sym}-{h.get('function')}-{h.get('interval')}",
                "type": "drift",
                "severity": "info",
                "title": f"DRIFT — {sym} past average hold time",
                "body": f"{sym} ({h.get('function')}/{h.get('interval')}) is at {hold_pct:.0f}% of its average hold time.",
                "target_page": "holdings",
                "ticker": sym,
            })
        rr = h.get("rr_dynamic")
        siblings = h.get("same_asset_siblings") or []
        if rr is not None and rr < 0 and not siblings:
            alerts.append({
                "id": f"negative-rr-{sym}-{h.get('function')}-{h.get('interval')}",
                "type": "negative_rr_uncovered",
                "severity": "warning",
                "title": f"Negative R:R, no covering sibling — {sym}",
                "body": (
                    f"{sym} ({h.get('function')}/{h.get('interval')}) has R:R Dynamic {rr:.2f} "
                    "and no same-asset sibling signal covering the position."
                ),
                "target_page": "holdings",
                "ticker": sym,
            })
    return alerts


def _eviction_alerts(days: int = 3) -> list[dict[str, Any]]:
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = book_snapshot_store.read_evictions(start_date=cutoff)
    except Exception:
        return []
    alerts: list[dict[str, Any]] = []
    for row in rows:
        evicted = row.get("evicted_ticker")
        challenger = row.get("challenger_ticker")
        alerts.append({
            "id": f"eviction-{evicted}-{row.get('snapshot_date')}",
            "type": "eviction",
            "severity": "info",
            "title": f"Evicted — {evicted}",
            "body": f"{evicted} evicted by challenger {challenger} on {row.get('snapshot_date')} (1C/A2, mode={row.get('mode')}).",
            "target_page": "holdings",
            "ticker": evicted,
        })
    return alerts


def get_alerts(
    book_id: str = "model",
    book: str = "enhanced",
    scenario: str = "normal",
) -> dict[str, Any]:
    alerts = (
        _correlation_alerts(scenario)
        + _conflict_alerts(book_id)
        + _holdings_alerts(book_id, book, scenario)
        + _eviction_alerts()
    )
    alerts.sort(key=lambda a: _SEVERITY_ORDER.get(a.get("severity", "info"), 3))
    return {
        "book_id": book_id,
        "as_of": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "alert_count": len(alerts),
        "alerts": alerts,
    }
