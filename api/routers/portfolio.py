"""Portfolio REST routes — Sizer + Risk."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import optional_api_key
from api.services import portfolio_service as svc

router = APIRouter(
    prefix="/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(optional_api_key)],
)


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class HoldingItem(BaseModel):
    symbol: str
    quantity: float


class AnalyzeHoldingsRequest(BaseModel):
    holdings: list[HoldingItem]
    cash_usd: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Sizer
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/sizer",
    operation_id="getPortfolioSizer",
    summary="Portfolio Sizer — full PortfolioResponse",
)
def get_sizer(
    scenario: str = Query(
        default="normal",
        description="Scenario: normal | stress | lowvol",
        pattern="^(normal|stress|lowvol)$",
    ),
) -> dict[str, Any]:
    """Return full regime-aware portfolio allocation payload.

    Includes ceiling decomposition, cluster budgets, per-position sizing,
    P&L enrichment, constraints, and active combo context.
    """
    try:
        return svc.get_portfolio_sizer(scenario=scenario)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Portfolio sizer computation failed: {exc}",
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Risk
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/risk",
    operation_id="getPortfolioRisk",
    summary="Portfolio Risk — cluster correlation matrix + breaches",
)
def get_risk() -> dict[str, Any]:
    """Return cluster-level correlation matrix, breach list, and cluster weight bars.

    Breaches: ρ > 0.75 = watch, ρ > 0.85 = action required.
    """
    try:
        return svc.get_portfolio_risk()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
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
    """Accept a user holdings list and return concentration warnings,
    correlation breaches, and suggested trims vs the model book.
    """
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
