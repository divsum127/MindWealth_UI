"""Portfolio REST routes — Sizer, Risk, Holdings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import optional_api_key
from api.services import portfolio_pipeline_service as pipeline_svc
from api.services import portfolio_service as svc
from api.services.portfolio_book import BookUnavailableError

router = APIRouter(
    prefix="/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(optional_api_key)],
)


class HoldingItem(BaseModel):
    symbol: str
    quantity: float


class AnalyzeHoldingsRequest(BaseModel):
    holdings: list[HoldingItem]
    cash_usd: float = 0.0


def _book_error(exc: Exception) -> HTTPException:
    if isinstance(exc, BookUnavailableError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# NAV overview (P0)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/nav",
    operation_id="getPortfolioNav",
    summary="Portfolio NAV overview — chart, attribution, admission snapshot",
)
def get_nav(
    book_id: str = Query(..., description="model | brokerage | personal"),
    book: str | None = Query(default=None, description="base | ssi | cv | enhanced (required for model; ignored for personal)"),
    scenario: str = Query(
        default="normal",
        description="Sizer scenario for consistency with holdings: normal | stress | lowvol | auto | manual",
        pattern="^(normal|stress|lowvol|auto|manual)$",
    ),
) -> dict[str, Any]:
    """Return overview NAV payload (HANDOFF §3). All MODEL valuation books when history source is wired."""
    try:
        return pipeline_svc.get_portfolio_nav(book_id, book, scenario=scenario)
    except (BookUnavailableError, ValueError) as exc:
        raise _book_error(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Portfolio NAV failed: {exc}",
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Holdings (P0)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/holdings",
    operation_id="getPortfolioHoldings",
    summary="Portfolio holdings with sizing, siblings, and quality fields",
)
def get_holdings(
    book_id: str = Query(..., description="model | brokerage | personal"),
    book: str | None = Query(default=None, description="base | ssi | cv | enhanced (required for model; ignored for personal)"),
    scenario: str = Query(
        default="normal",
        description="Sizer scenario for size_usd alignment: normal | stress | lowvol | auto | manual",
        pattern="^(normal|stress|lowvol|auto|manual)$",
    ),
) -> dict[str, Any]:
    """Return MODEL holdings merged with sizer allocations (HANDOFF §4)."""
    try:
        return pipeline_svc.get_portfolio_holdings(book_id, book, scenario=scenario)
    except (BookUnavailableError, ValueError) as exc:
        raise _book_error(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Portfolio holdings failed: {exc}",
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Sizer / Sizing (P0)
# ─────────────────────────────────────────────────────────────────────────────

def _sizer_response(
  scenario: str,
  book_id: str,
) -> dict[str, Any]:
    from api.services.portfolio_book import validate_model_only

    validate_model_only(book_id)
    payload = svc.get_portfolio_sizer(scenario=scenario)
    payload["book_id"] = book_id
    return payload


@router.get(
    "/sizer",
    operation_id="getPortfolioSizer",
    summary="Portfolio Sizer — full PortfolioResponse",
)
def get_sizer(
    book_id: str = Query(default="model", description="Must be model"),
    scenario: str = Query(
        default="normal",
        description="Scenario: normal | stress | lowvol | auto | manual",
        pattern="^(normal|stress|lowvol|auto|manual)$",
    ),
) -> dict[str, Any]:
    """Return full regime-aware portfolio allocation payload."""
    try:
        return _sizer_response(scenario, book_id)
    except BookUnavailableError as exc:
        raise _book_error(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Portfolio sizer computation failed: {exc}",
        ) from exc


@router.get(
    "/sizing",
    operation_id="getPortfolioSizing",
    summary="Portfolio Sizing — alias for /portfolio/sizer (July spec)",
    include_in_schema=True,
)
def get_sizing(
    book_id: str = Query(default="model", description="Must be model"),
    scenario: str = Query(
        default="normal",
        description="Scenario: normal | stress | lowvol | auto | manual",
        pattern="^(normal|stress|lowvol|auto|manual)$",
    ),
) -> dict[str, Any]:
    """Alias for sizer. `auto` regime-picks normal/stress/lowvol from the live ceiling chain;
    `manual` applies persisted user $ overrides on top of `normal` (D4)."""
    return get_sizer(book_id=book_id, scenario=scenario)


class ManualOverrideRequest(BaseModel):
    ticker: str
    allocation_usd: float
    function: str | None = None
    interval: str | None = None
    direction: str | None = "Long"


@router.get(
    "/sizing/manual-overrides",
    operation_id="listManualSizingOverrides",
    summary="List persisted MANUAL scenario size overrides",
)
def list_manual_overrides() -> dict[str, Any]:
    from api.services import manual_overrides_service

    return {"overrides": manual_overrides_service.list_overrides()}


@router.post(
    "/sizing/manual-overrides",
    operation_id="setManualSizingOverride",
    summary="Set a MANUAL scenario size override for one position",
)
def set_manual_override(body: ManualOverrideRequest) -> dict[str, Any]:
    from api.services import manual_overrides_service

    try:
        return manual_overrides_service.set_override(
            ticker=body.ticker,
            allocation_usd=body.allocation_usd,
            function=body.function,
            interval=body.interval,
            direction=body.direction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/sizing/manual-overrides",
    operation_id="removeManualSizingOverride",
    summary="Remove a MANUAL scenario size override",
)
def remove_manual_override(
    ticker: str = Query(...),
    function: str | None = Query(default=None),
    interval: str | None = Query(default=None),
    direction: str = Query(default="Long"),
) -> dict[str, Any]:
    from api.services import manual_overrides_service

    removed = manual_overrides_service.remove_override(
        ticker=ticker, function=function, interval=interval, direction=direction,
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found.")
    return {"removed": True}


# ─────────────────────────────────────────────────────────────────────────────
# Personal book CRUD (Phase 7) — book_id=personal holdings/cash storage
# ─────────────────────────────────────────────────────────────────────────────

class PersonalHoldingRequest(BaseModel):
    ticker: str
    shares: float
    cost_basis: float
    entry_date: str | None = None
    currency: str = "USD"
    notes: str | None = None


class PersonalCashRequest(BaseModel):
    cash_usd: float


@router.get(
    "/personal/holdings",
    operation_id="listPersonalHoldings",
    summary="List raw personal-book holdings (unpriced)",
)
def list_personal_holdings() -> dict[str, Any]:
    from api.services import personal_book_service

    return {"holdings": personal_book_service.list_holdings(), "cash_usd": personal_book_service.get_cash()}


@router.post(
    "/personal/holdings",
    operation_id="upsertPersonalHolding",
    summary="Add or update one personal-book holding",
)
def upsert_personal_holding(body: PersonalHoldingRequest) -> dict[str, Any]:
    from api.services import personal_book_service

    try:
        return personal_book_service.upsert_holding(
            ticker=body.ticker,
            shares=body.shares,
            cost_basis=body.cost_basis,
            entry_date=body.entry_date,
            currency=body.currency,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/personal/holdings",
    operation_id="removePersonalHolding",
    summary="Remove one personal-book holding",
)
def remove_personal_holding(ticker: str = Query(...)) -> dict[str, Any]:
    from api.services import personal_book_service

    removed = personal_book_service.remove_holding(ticker)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found.")
    return {"removed": True}


@router.put(
    "/personal/cash",
    operation_id="setPersonalCash",
    summary="Set personal-book cash balance",
)
def set_personal_cash(body: PersonalCashRequest) -> dict[str, Any]:
    from api.services import personal_book_service

    try:
        cash = personal_book_service.set_cash(body.cash_usd)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"cash_usd": cash}


# ─────────────────────────────────────────────────────────────────────────────
# Alerts (Phase 6) — cross-page feed built from data already computed elsewhere
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/alerts",
    operation_id="getPortfolioAlerts",
    summary="Cross-page alert feed: correlation breaches, conflicts, DRIFT, evictions",
)
def get_alerts(
    book_id: str = Query(default="model"),
    book: str = Query(default="enhanced"),
    scenario: str = Query(default="normal", pattern="^(normal|stress|lowvol|auto|manual)$"),
) -> dict[str, Any]:
    from api.services import alerts_service

    try:
        return alerts_service.get_alerts(book_id=book_id, book=book, scenario=scenario)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Alerts failed: {exc}",
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Regime-bucket daily series (A1) — served from Phase 1's book-state snapshot store
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/regime-history",
    operation_id="getPortfolioRegimeHistory",
    summary="Regime-bucket daily series — what Ahil's A1 four-book re-run reports against",
)
def get_regime_history(
    scenario: str = Query(default="normal", pattern="^(normal|stress|lowvol)$"),
    start_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD"),
) -> dict[str, Any]:
    """No history before the daily snapshot job's first run date — never backfilled."""
    try:
        return pipeline_svc.get_regime_history(scenario=scenario, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Regime history failed: {exc}",
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Risk
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/risk",
    operation_id="getPortfolioRisk",
    summary="Portfolio Risk — cluster correlation matrix + breaches",
)
def get_risk(
    book_id: str = Query(default="model", description="Must be model"),
    scenario: str = Query(
        default="normal",
        description="Sizer scenario for cluster weights: normal | stress | lowvol | auto | manual",
        pattern="^(normal|stress|lowvol|auto|manual)$",
    ),
) -> dict[str, Any]:
    """Return cluster-level correlation matrix, breach list, and cluster weight bars."""
    try:
        from api.services.portfolio_book import validate_model_only

        validate_model_only(book_id)
        payload = svc.get_portfolio_risk(scenario=scenario)
        payload["book_id"] = book_id
        return payload
    except BookUnavailableError as exc:
        raise _book_error(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Portfolio risk computation failed: {exc}",
        ) from exc


@router.post(
    "/risk/analyze",
    operation_id="analyzeUserHoldings",
    summary="Analyze user holdings vs model book",
    status_code=status.HTTP_200_OK,
)
def analyze_holdings(body: AnalyzeHoldingsRequest) -> dict[str, Any]:
    """Accept a user holdings list and return concentration warnings and correlation breaches."""
    try:
        holdings_dicts = [{"symbol": h.symbol, "quantity": h.quantity} for h in body.holdings]
        return svc.analyze_user_holdings(holdings=holdings_dicts, cash_usd=body.cash_usd)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Holdings analysis failed: {exc}",
        ) from exc


@router.get(
    "/risk/search",
    operation_id="searchPortfolioTickers",
    summary="Ticker autocomplete for holdings entry",
)
def search_tickers(
    q: str = Query(..., description="Partial ticker string, e.g. 'NVD'"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Return matching tickers from the open VT book and conviction universe."""
    if len(q.strip()) < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query 'q' must not be empty.")
    try:
        return svc.search_tickers(q=q, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ticker search failed: {exc}",
        ) from exc
