"""Trade-store report REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import optional_api_key
from api.services import reports_service as svc
from api.services import signal_enrichment_service as enrich_svc
from api.services import degradation_service as degrade_svc

router = APIRouter(prefix="/signals", tags=["signals"], dependencies=[Depends(optional_api_key)])


@router.get("/reports", operation_id="list_signal_reports")
def list_reports() -> list[dict[str, Any]]:
    return svc.list_available_reports()


_ALL_SIGNAL_SLUGS = frozenset({"all-signal", "all_signal"})


@router.get("/reports/{report_name}/latest", operation_id="get_latest_signal_report")
def get_latest_report(
    report_name: str,
    enrich: bool | None = Query(
        default=None,
        description=(
            "Inject supplementary surface fields. "
            "Defaults to false for all-signal (large dataset), true for outstanding/new."
        ),
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        description="Maximum number of records to return (applied after enrichment).",
    ),
) -> dict[str, Any]:
    effective_enrich = enrich if enrich is not None else report_name not in _ALL_SIGNAL_SLUGS
    try:
        payload = svc.load_report_records(report_name, enrich=effective_enrich)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if limit is not None:
        payload["records"] = payload["records"][:limit]
        payload["returned_count"] = len(payload["records"])
    return payload


@router.get("/reports/{report_name}/{report_date}", operation_id="get_dated_signal_report")
def get_dated_report(
    report_name: str,
    report_date: str,
    enrich: bool | None = Query(
        default=None,
        description=(
            "Inject supplementary surface fields. "
            "Defaults to false for all-signal (large dataset), true for outstanding/new."
        ),
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        description="Maximum number of records to return (applied after enrichment).",
    ),
) -> dict[str, Any]:
    effective_enrich = enrich if enrich is not None else report_name not in _ALL_SIGNAL_SLUGS
    try:
        payload = svc.load_report_records(report_name, report_date=report_date, enrich=effective_enrich)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if limit is not None:
        payload["records"] = payload["records"][:limit]
        payload["returned_count"] = len(payload["records"])
    return payload


@router.get("/shortlist", operation_id="get_claude_shortlist")
def get_shortlist() -> dict[str, Any]:
    return svc.get_shortlist_report()


@router.get("/strategy-health", operation_id="get_strategy_health")
def get_strategy_health(
    report_date: str | None = Query(default=None, description="YYYY-MM-DD trade_store date"),
) -> dict[str, Any]:
    try:
        return svc.strategy_health_report(report_date=report_date)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/gate-a2b",
    operation_id="get_gate_a2b_gating",
    summary="Gate A2b forward WR gating per function/interval/direction",
)
def get_gate_a2b_gating(
    report_date: str | None = Query(default=None, description="YYYY-MM-DD trade_store date"),
) -> dict[str, Any]:
    """
    Return approve/disapprove for every function/interval/direction combo using
    Gate A2b: forward testing win rate must be >= 60% (Across ALL Assets).

    Missing forward WR does not disapprove (field absence is not a failure).
    """
    try:
        return svc.gate_a2b_gating_report(report_date=report_date)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/surface", operation_id="get_signal_surface")
def get_signal_surface(
    report: str = Query(
        default="outstanding-signals",
        description="Signal report to enrich: outstanding-signals | new-signals | all-signal",
    ),
    report_date: str | None = Query(default=None, description="YYYY-MM-DD (defaults to latest)"),
) -> dict[str, Any]:
    """
    Return enriched per-signal surface fields for bubble chart + ranked cards.

    Adds to each row: composite_score, window_remaining_pct, tier, exit_fired,
    alpha_interpretation, er_annualized, signal_alpha_annualized, mtm_pct,
    days_elapsed, avg_hold_days, conviction_bq_score, conviction_fs_class.

    All values are Python-computed from CSV columns — no mock data.
    """
    try:
        payload = svc.load_report_records(report, report_date=report_date, enrich=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "report": report,
        "report_date": payload.get("report_date"),
        "source_file": payload.get("source_file"),
        "row_count": payload.get("row_count", 0),
        "records": payload.get("records", []),
    }


@router.get("/summary", operation_id="get_signal_summary")
def get_signal_summary(
    report: str = Query(
        default="outstanding-signals",
        description="outstanding-signals | new-signals | all-signal",
    ),
    report_date: str | None = Query(default=None, description="YYYY-MM-DD (defaults to latest)"),
) -> dict[str, Any]:
    """
    Return sidebar KPI counts derived from enriched signal records.

    Fields: total, long, short, exited, tier_counts, function_counts.
    """
    try:
        payload = svc.load_report_records(report, report_date=report_date, enrich=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    records = payload.get("records", [])
    summary = enrich_svc.compute_signal_summary(records)
    return {
        "report": report,
        "report_date": payload.get("report_date"),
        **summary,
    }


@router.post(
    "/check-degradation",
    operation_id="check_signal_degradation",
    summary="Layer 1 degradation alert check",
)
def check_signal_degradation() -> dict[str, Any]:
    """
    Run Layer 1 degradation analysis across all (asset/function/interval/direction) combos.

    Triggers fire when **any** of these conditions are met:

    - FWD win rate declining toward 60% while still >= 60% (DEGRADATION WATCH).
    - FWD win rate below 60% (DEGRADATION BREACH).
    - A booked loss exists on any virtual trading portfolio position (realised P&L < 0).
    - A live position's MTM exceeds -10%.

    On trigger, loss pattern is classified as asset-specific, function degradation,
    or a combo issue, and a recommendation is generated.
    """
    try:
        return degrade_svc.check_degradation()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Degradation check failed: {exc}",
        ) from exc


@router.get("/counts", operation_id="get_signal_counts")
def get_signal_counts(
    report_date: str | None = Query(default=None, description="YYYY-MM-DD (defaults to latest)"),
) -> dict[str, Any]:
    """
    Return sidebar navigation badge counts: outstanding, new, shortlist.
    Also includes tier breakdown for outstanding signals.
    """
    counts: dict[str, Any] = {}
    for slug in ("outstanding-signals", "new-signals"):
        try:
            payload = svc.load_report_records(slug, report_date=report_date, enrich=True)
            records = payload.get("records", [])
            summary = enrich_svc.compute_signal_summary(records)
            key = "outstanding" if "outstanding" in slug else "new"
            counts[key] = {
                "total": summary["total"],
                "long": summary["long"],
                "short": summary["short"],
                "exited": summary["exited"],
                "tier_counts": summary["tier_counts"],
            }
        except FileNotFoundError:
            key = "outstanding" if "outstanding" in slug else "new"
            counts[key] = {"total": 0, "long": 0, "short": 0, "exited": 0, "tier_counts": {}}
    # Shortlist count from existing service
    try:
        shortlist = svc.get_shortlist_report()
        counts["shortlist"] = {"total": shortlist.get("row_count", 0)}
    except Exception:
        counts["shortlist"] = {"total": 0}
    return {"report_date": report_date, **counts}
