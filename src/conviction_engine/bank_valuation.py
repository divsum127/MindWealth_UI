"""Bank-specific scoring & valuation substitutions (Conviction Engine v6, item 3).

Banks are naturally leveraged (deposits are liabilities), so the generic
net-debt/EBITDA balance-sheet check and EV/forward-revenue valuation driver used
for the other 5 business types are meaningless for them. This module implements
the bank-specific substitutions from the 28 July consolidated note (Section 5.7),
confirmed/superseded by Rohit's 30 July reply + the FS-slice follow-up:

- ``margin_quality`` -> efficiency ratio = noninterest expense / (net interest
  income + noninterest income).
- ``balance_sheet`` -> equity/assets ratio ("well-capitalized" test).
- ``roic_wacc_spread`` -> unchanged generic function, just fed ROE + a 9% bank
  cost of equity (see ``WACC_BY_TYPE["bank"]`` in ``fundamentals_enriched.py``).
- OEY -> net income / market cap (i.e. 1/PE) — substituted in ``engine.daily_update``.
- Valuation-tax ``entry_multiple`` -> P/TBV-vs-ROE excess-return model. This
  **supersedes** Rohit's 30 July reply, which gave a simpler flat Price/Book tier
  table — the FS-slice follow-up explicitly said to use "the consolidated note's
  method, it's the more rigorous one" instead. See ``conviction_fixes_decisions.md``.
"""

from __future__ import annotations

from typing import Any

from .scoring import _float_or_none

BANK_COST_OF_EQUITY = 0.09  # matches WACC_BY_TYPE["bank"] in fundamentals_enriched.py
BANK_SUSTAINABLE_GROWTH = 0.03  # long-run nominal book-value growth assumption for a mature bank

# Actual/fair P/TBV ratio tiers -> valuation-tax points (entry_multiple substitution).
# At/below fair value -> no tax; each ~25pp of overvaluation adds another point.
PTBV_PREMIUM_TIERS: tuple[tuple[float, float], ...] = (
    (1.00, 0.0),
    (1.25, -1.0),
    (1.50, -2.0),
    (2.00, -3.0),
    (2.50, -4.0),
)
PTBV_PREMIUM_FLOOR = -5.0  # matches other business types' worst-case entry_multiple tax

EFFICIENCY_RATIO_STRONG = 0.55
EFFICIENCY_RATIO_WEAK = 0.65

EQUITY_ASSETS_WELL_CAPITALIZED = 0.10
EQUITY_ASSETS_ADEQUATE = 0.06


def compute_equity_assets_ratio(financials: dict[str, Any]) -> float | None:
    equity = _float_or_none(financials.get("stockholders_equity"))
    assets = _float_or_none(financials.get("total_assets"))
    if equity is None or not assets:
        return None
    return equity / assets


def score_bank_balance_sheet(financials: dict[str, Any]) -> tuple[float, str]:
    """Equity/assets ratio -> BQ ``balance_sheet`` substitution + a purpose-style label."""
    ratio = compute_equity_assets_ratio(financials)
    if ratio is None:
        return 0.0, "bank_unknown"
    if ratio > EQUITY_ASSETS_WELL_CAPITALIZED:
        return 1.0, "bank_well_capitalized"
    if ratio >= EQUITY_ASSETS_ADEQUATE:
        return 0.0, "bank_adequately_capitalized"
    return -2.0, "bank_thinly_capitalized"


def compute_efficiency_ratio(financials: dict[str, Any]) -> float | None:
    noninterest_expense = _float_or_none(financials.get("noninterest_expense_ttm"))
    net_interest_income = _float_or_none(financials.get("net_interest_income_ttm"))
    noninterest_income = _float_or_none(financials.get("noninterest_income_ttm")) or 0.0
    if noninterest_expense is None or net_interest_income is None:
        return None
    revenue_base = net_interest_income + noninterest_income
    if revenue_base <= 0:
        return None
    return noninterest_expense / revenue_base


def score_bank_margin_quality(financials: dict[str, Any]) -> float:
    ratio = compute_efficiency_ratio(financials)
    if ratio is None:
        return 0.0
    if ratio < EFFICIENCY_RATIO_STRONG:
        return 2.0
    if ratio <= EFFICIENCY_RATIO_WEAK:
        return 0.0
    return -2.0


def compute_tangible_book_value(financials: dict[str, Any]) -> float | None:
    """Stockholders' equity net of goodwill/intangibles.

    Falls back to yfinance's reported per-share book value * shares outstanding
    when balance-sheet goodwill/intangibles line items aren't available.
    Documented gap: that fallback does not strip intangibles, so it can overstate
    TBV for acquisitive banks — see ``conviction_fixes_decisions.md``.
    """
    equity = _float_or_none(financials.get("stockholders_equity"))
    goodwill = _float_or_none(financials.get("goodwill")) or 0.0
    intangibles = _float_or_none(financials.get("other_intangible_assets")) or 0.0
    if equity is not None:
        return max(0.0, equity - goodwill - intangibles)

    book_value_per_share = _float_or_none(financials.get("book_value_per_share"))
    shares = _float_or_none(financials.get("shares_outstanding_now"))
    if book_value_per_share is not None and shares:
        return book_value_per_share * shares
    return None


def fair_ptbv(
    roe: float | None,
    *,
    cost_of_equity: float = BANK_COST_OF_EQUITY,
    growth: float = BANK_SUSTAINABLE_GROWTH,
) -> float | None:
    """Gordon-growth excess-return P/TBV: ``(ROE - g) / (Cost of equity - g)``."""
    if roe is None:
        return None
    denom = cost_of_equity - growth
    if denom <= 0:
        return None
    return max(0.0, (roe - growth) / denom)


def _actual_and_fair_ptbv(record: dict[str, Any]) -> dict[str, Any]:
    market_cap = _float_or_none(record.get("market_cap"))
    tbv = _float_or_none(record.get("tangible_book_value"))
    roe = _float_or_none(record.get("roic_5y_avg"))

    breakdown: dict[str, Any] = {"actual_ptbv": None, "fair_ptbv": None, "ratio": None, "roe": roe}
    if market_cap is None or not tbv or tbv <= 0:
        return breakdown

    actual = market_cap / tbv
    fair = fair_ptbv(roe)
    breakdown["actual_ptbv"] = round(actual, 3)
    breakdown["fair_ptbv"] = round(fair, 3) if fair is not None else None
    if fair and fair > 0:
        breakdown["ratio"] = round(actual / fair, 3)
    return breakdown


def bank_ptbv_valuation_tax(record: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """P/TBV-vs-ROE valuation-tax substitution for the ``entry_multiple`` component.

    Returns ``(points, breakdown)`` — ``breakdown`` carries the actual/fair P/TBV
    and their ratio for API/UI transparency (Engine Layers click-through, item 19).
    """
    breakdown = _actual_and_fair_ptbv(record)
    ratio = breakdown.get("ratio")
    if ratio is None:
        return 0.0, breakdown

    points = 0.0
    for threshold, penalty in PTBV_PREMIUM_TIERS:
        if ratio >= threshold:
            points = penalty
    return max(PTBV_PREMIUM_FLOOR, points), breakdown


def bank_fs_valuation_slice(record: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """FS-score daily valuation-slice row for banks (item 13).

    Symmetric version of the same P/TBV-vs-ROE model — cheap (ratio well below
    fair) adds, expensive subtracts, unlike the always-<=0 valuation tax.
    """
    breakdown = _actual_and_fair_ptbv(record)
    ratio = breakdown.get("ratio")
    if ratio is None:
        return 0.0, breakdown
    if ratio <= 0.7:
        return 10.0, breakdown
    if ratio <= 1.0:
        return 5.0, breakdown
    if ratio <= 1.5:
        return 0.0, breakdown
    if ratio <= 2.0:
        return -5.0, breakdown
    return -10.0, breakdown
