"""Shared Business Quality dimension scoring (Conviction Engine v6)."""

from __future__ import annotations

from typing import Any

from .models import BusinessType
from .scoring import _float_or_none

NET_DEBT_SAFE = {
    BusinessType.SAAS.value: 0.0,
    BusinessType.COMPOUNDER.value: 1.5,
    BusinessType.INCOME.value: 2.5,
    BusinessType.CYCLICAL.value: 1.0,
    BusinessType.UNKNOWN.value: 1.5,
}
NET_DEBT_CONCERN = {
    BusinessType.SAAS.value: 1.5,
    BusinessType.COMPOUNDER.value: 3.0,
    BusinessType.INCOME.value: 5.0,
    BusinessType.CYCLICAL.value: 3.5,
    BusinessType.UNKNOWN.value: 3.0,
}
NET_DEBT_DANGER = {
    BusinessType.SAAS.value: 5.0,
    BusinessType.COMPOUNDER.value: 5.0,
    BusinessType.INCOME.value: 7.0,
    BusinessType.CYCLICAL.value: 3.5,
    BusinessType.UNKNOWN.value: 5.0,
}

# Manual 0–10 analyst scores → BQ points
def score_manual_analyst(value: Any, *, low: float = 4.0, high: float = 7.0) -> float:
    """Map analyst 0–10 score to BQ dimension points (-1 / 0 / +2)."""
    v = _float_or_none(value)
    if v is None:
        return 0.0
    if v >= high:
        return 2.0
    if v >= low:
        return 0.0
    return -1.0


def score_macro_tailwind(overrides: dict[str, Any]) -> float:
    """Agent or manual macro score: -1, 0, +1, +2 stored in macro_tailwind or macro_tailwind_score."""
    raw = overrides.get("macro_tailwind")
    if raw is None and isinstance(overrides.get("macro_tailwind_detail"), dict):
        raw = overrides["macro_tailwind_detail"].get("score")
    v = _float_or_none(raw)
    if v is None:
        return 0.0
    return float(max(-1.0, min(2.0, v)))


def classify_debt_purpose(financials: dict[str, Any]) -> str:
    """
    financial_engineering | capex_cycle | operational
    """
    net_debt = _float_or_none(financials.get("net_debt_stored"))
    total_cash = _float_or_none(financials.get("cash_and_equivalents"))
    total_debt = _float_or_none(financials.get("total_debt"))
    if total_cash is not None and total_debt is not None:
        net_cash = total_cash - total_debt
    elif net_debt is not None:
        net_cash = -net_debt
    else:
        net_cash = None

    if net_cash is not None and net_cash > 0:
        return "financial_engineering"

    rev = _float_or_none(financials.get("revenue_ttm")) or _float_or_none(financials.get("fwd_revenue_stored"))
    capex_now = abs(_float_or_none(financials.get("capex_ttm")) or 0.0)
    capex_3y = abs(_float_or_none(financials.get("capex_3y_ago")) or 0.0)
    rev_3y = _float_or_none(financials.get("revenue_3y_ago"))
    if rev and rev > 0:
        ratio_now = capex_now / rev
        ratio_3y = (capex_3y / rev_3y) if rev_3y and rev_3y > 0 else ratio_now
        if ratio_3y > 0 and ratio_now / max(ratio_3y, 1e-6) > 2.0:
            return "capex_cycle"
    return "operational"


def score_debt_maturity_risk(financials: dict[str, Any], business_type: str, overrides: dict[str, Any]) -> float:
    manual = overrides.get("debt_maturity_risk")
    if manual is not None:
        return float(manual)
    st_pct = _float_or_none(financials.get("short_term_debt_pct"))
    nd_ebitda = _float_or_none(financials.get("net_debt_ebitda"))
    if st_pct is None:
        return 0.0
    safe = NET_DEBT_SAFE.get(business_type, NET_DEBT_SAFE[BusinessType.UNKNOWN.value])
    if st_pct > 0.5 and nd_ebitda is not None and nd_ebitda > safe:
        return -1.0
    return 0.0


def score_balance_sheet_v6(
    financials: dict[str, Any],
    business_type: str,
    overrides: dict[str, Any] | None = None,
) -> tuple[float, str]:
    """
    Balance sheet BQ score and debt_purpose classification.
    """
    overrides = overrides or {}
    if overrides.get("balance_sheet") is not None:
        purpose = str(overrides.get("debt_purpose") or classify_debt_purpose(financials))
        return float(overrides["balance_sheet"]), purpose

    purpose = classify_debt_purpose(financials)
    if purpose == "financial_engineering":
        return 2.0, purpose

    nd_ebitda = _float_or_none(financials.get("net_debt_ebitda"))
    safe = NET_DEBT_SAFE.get(business_type, NET_DEBT_SAFE[BusinessType.UNKNOWN.value])
    concern = NET_DEBT_CONCERN.get(business_type, NET_DEBT_CONCERN[BusinessType.UNKNOWN.value])
    danger = NET_DEBT_DANGER.get(business_type, NET_DEBT_DANGER[BusinessType.UNKNOWN.value])

    if purpose == "capex_cycle":
        st_pct = _float_or_none(financials.get("short_term_debt_pct")) or 0.0
        if st_pct > 0.5:
            return -1.0, purpose
        if overrides.get("debt_purpose_forward") == "capex_cycle_expected":
            return -1.0, purpose
        return 0.0, purpose

    if nd_ebitda is None:
        return 0.0, purpose
    if nd_ebitda <= safe:
        return 1.0, purpose
    if nd_ebitda <= concern:
        return 0.0, purpose
    if nd_ebitda <= danger:
        return -1.0, purpose
    return -2.0, purpose


def detect_divergence_signal(
    *,
    current_price: float | None,
    fifty_two_week_high: float | None,
    price_history: Any = None,
    days_below_high: int | None = None,
    fd_direction: str | None = None,
    manual_flag: bool | None = None,
    ticker: str | None = None,
) -> bool:
    """Delegate to persistent divergence module (July 2026 spec)."""
    from .divergence import detect_divergence_signal as _detect

    # Bootstrap days counter from price history when store has no persisted state yet
    if days_below_high is None and price_history is not None and current_price and fifty_two_week_high:
        try:
            import pandas as pd

            series = price_history["Close"] if isinstance(price_history, pd.DataFrame) else price_history
            threshold = fifty_two_week_high * 0.85
            if hasattr(series, "dropna") and current_price <= threshold:
                clean = series.dropna().sort_index()
                above = clean >= threshold
                if not above.any():
                    days_below_high = len(clean)
                else:
                    last_above = clean.index[above][-1]
                    days_below_high = (clean.index[-1] - last_above).days
        except Exception:
            pass

    return _detect(
        current_price=current_price,
        fifty_two_week_high=fifty_two_week_high,
        days_below_high=days_below_high,
        fd_direction=fd_direction,
        manual_flag=manual_flag,
        ticker=ticker,
    )


def score_margin_quality_cyclical(fcf_margin: float | None, revenue_growth: float | None) -> float:
    if fcf_margin is not None and fcf_margin > 0 and (revenue_growth or 0) > 0:
        return 1.0
    if fcf_margin is not None and fcf_margin < 0:
        return -1.0
    return 0.0
