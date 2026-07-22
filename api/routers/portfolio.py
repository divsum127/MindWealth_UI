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
    book: str = Query(..., description="base | ssi | cv | enhanced (required for model)"),
    scenario: str = Query(
        default="normal",
        description="Sizer scenario for consistency with holdings: normal | stress | lowvol",
        pattern="^(normal|stress|lowvol)$",
    ),
) -> dict[str, Any]:
    """Return overview NAV payload (HANDOFF §3). MODEL enhanced only until four-book replay."""
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
    book: str = Query(..., description="base | ssi | cv | enhanced (required for model)"),
    scenario: str = Query(
        default="normal",
        description="Sizer scenario for size_usd alignment: normal | stress | lowvol",
        pattern="^(normal|stress|lowvol)$",
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
        description="Scenario: normal | stress | lowvol",
        pattern="^(normal|stress|lowvol)$",
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
        description="Scenario: normal | stress | lowvol | auto",
        pattern="^(normal|stress|lowvol|auto)$",
    ),
) -> dict[str, Any]:
    """Alias for sizer; `auto` maps to `normal` until AUTO scenario is specified."""
    effective = "normal" if scenario == "auto" else scenario
    return get_sizer(book_id=book_id, scenario=effective)


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
        description="Sizer scenario for cluster weights: normal | stress | lowvol",
        pattern="^(normal|stress|lowvol)$",
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
