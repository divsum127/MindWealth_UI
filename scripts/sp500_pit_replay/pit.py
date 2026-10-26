"""Point-in-time fundamentals for the BQ replay (CE-29).

Every value is the one a reader could have seen on the test date: only facts filed on or
before it, and of those the one filed first for each period (later restatements ignored).
Durations use the latest fiscal year (10-K, ~1 year); balance-sheet items the latest instant.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.conviction_engine.models import BusinessType


def _d(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _first_filed(rows: list[dict[str, Any]], as_of: date, *, annual: bool) -> dict[tuple, dict[str, Any]]:
    best: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        filed = _d(r.get("filed"))
        if filed is None or filed > as_of:
            continue
        start, end = _d(r.get("start")), _d(r.get("end"))
        if end is None:
            continue
        if annual:
            if start is None or not (330 <= (end - start).days <= 400):
                continue
        key = (r.get("start"), r.get("end"))
        if key not in best or (r.get("filed") or "") < (best[key].get("filed") or ""):
            best[key] = r
    return best


def annual_series(rows: list[dict[str, Any]], as_of: date) -> list[float]:
    """Fiscal-year values known at as_of, newest first."""
    best = _first_filed(rows, as_of, annual=True)
    return [v["val"] for _, v in sorted(best.items(), key=lambda kv: kv[0][1], reverse=True)]


def latest_instant(rows: list[dict[str, Any]], as_of: date) -> float | None:
    best = _first_filed([r for r in rows if not r.get("start")], as_of, annual=False)
    if not best:
        return None
    return max(best.items(), key=lambda kv: kv[0][1])[1]["val"]


def fundamentals_as_of(facts: dict[str, list[dict[str, Any]]], as_of: date, price: float | None) -> dict[str, Any] | None:
    get = lambda k: annual_series(facts.get(k) or [], as_of)  # noqa: E731
    revenue = get("revenue")
    if len(revenue) < 2 or revenue[0] <= 0:
        return None
    out: dict[str, Any] = {"revenue_ttm": revenue[0], "revenue_growth": revenue[0] / revenue[1] - 1 if revenue[1] > 0 else None}
    if len(revenue) >= 3 and revenue[2] > 0 and revenue[1] > 0:
        out["revenue_accelerating"] = (revenue[0] / revenue[1]) > (revenue[1] / revenue[2])

    gp, cogs = get("gross_profit"), get("cost_of_revenue")
    gross = [g for g in gp] if gp else [r - c for r, c in zip(revenue, cogs)] if cogs else []
    if gross:
        gm = [g / r for g, r in zip(gross, revenue) if r > 0]
        if gm:
            out["gross_margin"] = gm[0]
        if len(gm) >= 2:
            out["gross_margin_trend"] = gm[0] - gm[1]

    ni = get("net_income")
    if ni:
        out["net_income_ttm"] = ni[0]
        out["net_margin"] = ni[0] / revenue[0]
    cfo, capex = get("cfo"), get("capex")
    if cfo:
        fcf = cfo[0] - (capex[0] if capex else 0.0)
        out["fcf_ttm"] = fcf
        out["fcf_margin"] = fcf / revenue[0]

    oi, da = get("operating_income"), get("d_and_a")
    ebitda = (oi[0] + (da[0] if da else 0.0)) if oi else None
    debt = sum(v for v in (latest_instant(facts.get("long_term_debt") or [], as_of),
                           latest_instant(facts.get("short_term_debt") or [], as_of)) if v)
    cash = latest_instant(facts.get("cash") or [], as_of) or 0.0
    equity = latest_instant(facts.get("equity") or [], as_of)
    net_debt = debt - cash
    out["net_debt_stored"] = net_debt
    if ebitda and ebitda > 0:
        out["ebitda_ttm"] = ebitda
        out["net_debt_ebitda"] = net_debt / ebitda
    if oi and equity and (debt + equity) > 0:
        tax, pre = get("income_tax"), get("pretax_income")
        rate = tax[0] / pre[0] if tax and pre and pre[0] > 0 else 0.25
        rate = min(max(rate, 0.0), 0.35)
        out["roic_proxy"] = oi[0] * (1 - rate) / (debt + equity)

    buy, div = get("buybacks"), get("dividends_paid")
    if len(buy) >= 1:
        out["buyback_spend_ttm"] = buy[0]
    if len(buy) >= 2:
        out["buyback_spend_prior_year"] = buy[1]
    if div and ni and div[0] > 0:
        out["distribution_coverage_ratio"] = ni[0] / div[0]

    shares = get("shares")
    if price and shares and shares[0] > 0:
        mcap = price * shares[0]
        out["market_cap"] = mcap
        out["price"] = price
        out["fwd_revenue_stored"] = revenue[0]  # trailing revenue stands in for forward
        out["ev_fwd_rev"] = (mcap + net_debt) / revenue[0]
        if ebitda and ebitda > 0:
            out["ev_fwd_ebitda"] = (mcap + net_debt) / ebitda
        if ni and ni[0] > 0:
            out["pe_ttm"] = mcap / ni[0]
            out["owner_earnings_yield"] = (out.get("fcf_ttm") or ni[0]) / mcap
    return out


def business_type_from_sic(sic: str | None, net_margin: float | None) -> str:
    """Coarse SIC → business type for names not in today's store (stated in the report)."""
    try:
        code = int(sic or 0)
    except ValueError:
        code = 0
    if 6020 <= code <= 6036:
        return BusinessType.BANK.value
    if 7370 <= code <= 7379:
        return BusinessType.SAAS.value
    if 4810 <= code <= 4899:
        return BusinessType.TELCO.value
    if 4900 <= code <= 4949:
        return BusinessType.REGULATED_UTILITY.value
    if code == 6798:
        return BusinessType.INCOME.value
    if code in (3674, 3672, 3577, 3576, 3571, 3572, 3661, 3663):
        return BusinessType.HIGH_MARGIN_HARDWARE.value if (net_margin or 0) >= 0.40 else BusinessType.CYCLICAL.value
    if 1000 <= code <= 1499 or 2800 <= code <= 2999 or 3300 <= code <= 3399 or 1311 <= code <= 1389:
        return BusinessType.CYCLICAL.value
    if 6300 <= code <= 6411:
        return BusinessType.UNKNOWN.value  # insurers: coverage incomplete
    return BusinessType.COMPOUNDER.value
