"""Enriched fundamentals extraction from yfinance financial statements."""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

from .bq_scoring import (
    detect_divergence_signal,
    score_balance_sheet_v6,
    score_debt_maturity_risk,
    score_macro_tailwind,
    score_margin_quality_cyclical,
)
from .dividend_yield import compute_dividend_yield_stats
from .fd_votes import compute_fd_votes
from .pe_history_core import (  # re-exported: existing `from .fundamentals_enriched import ...` callers keep working
    PE_HISTORY_MAX_STORED_POINTS,
    PE_HISTORY_TARGET_YEARS,
    compute_pe_history,
)
from .pe_history_fmp import fetch_pe_history_fmp, is_us_ticker
from .pe_history_sec import fetch_pe_history_sec
from .scoring import (
    BusinessType,
    _float_or_none,
    _normalise_dividend_yield,
    _score_insider,
    _score_reinvestment,
    score_manual,
)

logger = logging.getLogger(__name__)

WACC_BY_TYPE = {
    BusinessType.INCOME.value: 0.055,
    BusinessType.COMPOUNDER.value: 0.075,
    BusinessType.CYCLICAL.value: 0.09,
    BusinessType.SAAS.value: 0.10,
    BusinessType.UNKNOWN.value: 0.08,
}

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


def _safe_dict(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return dict(value)
    except Exception:
        return {}


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _df_row(df: pd.DataFrame | None, *row_labels: str) -> float | None:
    """Return the latest column value for the first matching income/balance/cashflow row.

    yfinance quarterly statement columns are newest-first — ``sort_index()`` before slicing
    so ``iloc[-1]`` is always the latest quarter regardless of raw column order (same bug class
    fixed for ``revenue_growth_yoy`` — see job-status 2026-07-22).
    """
    if df is None or df.empty:
        return None
    for label in row_labels:
        if label not in df.index:
            continue
        row = df.loc[label].dropna().sort_index()
        if row.empty:
            continue
        val = row.iloc[-1]
        if pd.isna(val):
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return None


def _df_ttm_sum(df: pd.DataFrame | None, *row_labels: str, periods: int = 4) -> float | None:
    """Sum the most recent ``periods`` quarters. See ``_df_row`` for the sort-order rationale."""
    if df is None or df.empty:
        return None
    for label in row_labels:
        if label not in df.index:
            continue
        row = df.loc[label].dropna().sort_index()
        if len(row) < 1:
            continue
        chunk = row.iloc[-periods:]
        try:
            return float(chunk.sum())
        except (TypeError, ValueError):
            continue
    return None


def fetch_yfinance_enriched(ticker: str, max_attempts: int = 3) -> dict[str, Any]:
    import yfinance as yf

    symbol = ticker.upper().strip()
    result: dict[str, Any] = {
        "ticker": symbol,
        "info": {},
        "fast_info": {},
        "errors": [],
    }

    yt = None
    last_exc: str | None = None
    for attempt in range(max_attempts):
        try:
            yt = yf.Ticker(symbol)
            break
        except Exception as exc:
            last_exc = str(exc)
            time.sleep(0.6 * (attempt + 1))
    if yt is None:
        result["errors"].append(f"Ticker init failed after {max_attempts}: {last_exc}")
        return result

    for attempt in range(max_attempts):
        try:
            result["info"] = _safe_dict(getattr(yt, "info", {}) or {})
            if result["info"] and len(result["info"]) > 2:
                break
        except Exception as exc:
            result["errors"].append(f"info attempt {attempt + 1}: {exc}")
        time.sleep(0.5 * (attempt + 1))
    if not result["info"]:
        result["errors"].append("info: empty after retries")

    try:
        result["fast_info"] = _safe_dict(getattr(yt, "fast_info", {}) or {})
    except Exception as exc:
        result["errors"].append(f"fast_info: {exc}")

    try:
        hist = yt.history(period="max", auto_adjust=False)
        if not hist.empty and "Close" in hist.columns:
            close = hist["Close"].dropna()
            if close.index.tz is not None:
                close.index = close.index.tz_localize(None)
            result["price_history"] = close
    except Exception as exc:
        result["errors"].append(f"history: {exc}")

    try:
        divs = getattr(yt, "dividends", pd.Series(dtype=float))
        if divs is not None and not divs.empty:
            if divs.index.tz is not None:
                divs.index = divs.index.tz_localize(None)
            result["dividends"] = divs
    except Exception as exc:
        result["errors"].append(f"dividends: {exc}")

    for stmt_name, attr in [
        ("quarterly_income", "quarterly_income_stmt"),
        ("quarterly_balance", "quarterly_balance_sheet"),
        ("quarterly_cashflow", "quarterly_cashflow"),
    ]:
        try:
            df = getattr(yt, attr, None)
            if df is not None and not df.empty:
                result[stmt_name] = df
        except Exception as exc:
            result["errors"].append(f"{stmt_name}: {exc}")

    return result


def _normalize_ratio(value: float | None) -> float | None:
    """Normalize yfinance ratios that may be percent-like (>5) or decimal."""
    if value is None:
        return None
    v = float(value)
    if abs(v) > 5:
        return v / 100.0
    return v


def compute_fd_direction(
    revenue_growth: float | None,
    eps_growth: float | None,
    margin_trend: float | None,
) -> str:
    """Legacy 3-signal FD; prefer compute_fd_votes for v6."""
    positive = 0
    negative = 0
    if revenue_growth is not None:
        if revenue_growth > 0.02:
            positive += 1
        elif revenue_growth < -0.02:
            negative += 1
    if eps_growth is not None:
        if eps_growth > 0.05:
            positive += 1
        elif eps_growth < -0.05:
            negative += 1
    if margin_trend is not None:
        if margin_trend > 0.01:
            positive += 1
        elif margin_trend < -0.01:
            negative += 1
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "stable"


def score_balance_sheet(net_debt_ebitda: float | None, business_type: str) -> float:
    if net_debt_ebitda is None:
        return 0.0
    safe = NET_DEBT_SAFE.get(business_type, NET_DEBT_SAFE[BusinessType.UNKNOWN.value])
    concern = NET_DEBT_CONCERN.get(business_type, NET_DEBT_CONCERN[BusinessType.UNKNOWN.value])
    danger = NET_DEBT_DANGER.get(business_type, NET_DEBT_DANGER[BusinessType.UNKNOWN.value])
    if net_debt_ebitda <= safe:
        return 1.0
    if net_debt_ebitda <= concern:
        return 0.0
    if net_debt_ebitda <= danger:
        return -1.0
    return -2.0


def score_margin_quality(
    business_type: str,
    revenue_growth: float | None,
    fcf_margin: float | None,
    distribution_coverage: float | None,
    gross_margin: float | None,
) -> float:
    if business_type == BusinessType.INCOME.value and distribution_coverage is not None:
        if distribution_coverage > 2.0:
            return 2.0
        if distribution_coverage >= 1.2:
            return 0.0
        return -1.0
    if business_type == BusinessType.CYCLICAL.value:
        return score_margin_quality_cyclical(fcf_margin, revenue_growth)
    rule_of_40 = ((revenue_growth or 0) + (fcf_margin or 0)) * 100
    if rule_of_40 >= 40:
        return 2.0
    if rule_of_40 >= 25:
        return 1.0
    if rule_of_40 >= 10:
        return 0.0
    if fcf_margin is not None and fcf_margin < 0:
        return -1.0
    if gross_margin is not None and gross_margin >= 0.40:
        return 0.5
    return 0.0


def score_revenue_quality(gross_margin: float | None, fcf_margin: float | None) -> float:
    if gross_margin is None and fcf_margin is None:
        return 0.0
    score = 0.0
    if gross_margin is not None:
        if gross_margin >= 0.50:
            score += 2.0
        elif gross_margin >= 0.35:
            score += 1.0
    if fcf_margin is not None:
        if fcf_margin >= 0.15:
            score += 1.0
        elif fcf_margin >= 0.05:
            score += 0.5
    return min(2.0, max(-2.0, score))


def score_growth_trajectory(revenue_growth: float | None, revenue_accel: bool | None) -> float:
    if revenue_growth is None:
        return 0.0
    if revenue_accel:
        if revenue_growth >= 0.20:
            return 2.0
        if revenue_growth >= 0.10:
            return 1.0
        if revenue_growth >= 0.03:
            return 0.0
        return -1.0
    if revenue_growth >= 0.15:
        return 2.0
    if revenue_growth >= 0.05:
        return 1.0
    if revenue_growth >= 0.0:
        return 0.0
    return -1.0


def score_roic_spread(roic: float | None, business_type: str) -> float:
    if roic is None:
        return 0.0
    wacc = WACC_BY_TYPE.get(business_type, WACC_BY_TYPE[BusinessType.UNKNOWN.value])
    spread = roic - wacc
    if spread >= 0.05:
        return 2.0
    if spread >= 0.02:
        return 1.0
    if spread > 0:
        return 0.0
    if spread >= -0.02:
        return -1.0
    return -2.0


def score_gross_margin_trend(margin_trend: float | None) -> float:
    if margin_trend is None:
        return 0.0
    if margin_trend >= 0.02:
        return 1.0
    if margin_trend <= -0.02:
        return -1.0
    return 0.0


def compute_bq_components_auto(
    fundamentals: dict[str, Any],
    business_type: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, float]:
    overrides = overrides or {}
    if isinstance(overrides.get("bq_components"), dict):
        return {str(k): float(v) for k, v in overrides["bq_components"].items()}

    rev_g = _float_or_none(fundamentals.get("revenue_growth"))
    fcf_m = _float_or_none(fundamentals.get("fcf_margin"))
    gross_m = _float_or_none(fundamentals.get("gross_margin"))
    nd_ebitda = _float_or_none(fundamentals.get("net_debt_ebitda"))
    roic = _float_or_none(_first_not_none(fundamentals.get("roic"), fundamentals.get("roic_proxy")))
    dist_cov = _float_or_none(fundamentals.get("distribution_coverage_ratio"))
    margin_trend = _float_or_none(fundamentals.get("gross_margin_trend"))
    rev_accel = fundamentals.get("revenue_accelerating")

    insider_val = overrides.get("insider_ownership", fundamentals.get("insider_pct"))
    reinvest_val = overrides.get("reinvestment_runway", fundamentals.get("reinvestment_runway"))

    bs_score, debt_purpose = score_balance_sheet_v6(fundamentals, business_type, overrides)
    fundamentals["debt_purpose"] = debt_purpose

    ceo_score = score_manual("ceo_quality_score", overrides)
    if overrides.get("ceo_quality_score") is None:
        from .ceo_quality import compute_ceo_quality_score

        ceo_score, ceo_detail = compute_ceo_quality_score(
            {"ticker": fundamentals.get("ticker"), **fundamentals},
            overrides,
        )
        if ceo_detail:
            overrides.setdefault("ceo_quality_detail", ceo_detail)

    moat_score = score_manual("competitive_moat_score", overrides)
    if overrides.get("competitive_moat_score") is None and isinstance(overrides.get("competitive_moat_detail"), dict):
        from .agent_dims import analyst_score_to_bq

        moat_score = analyst_score_to_bq(_float_or_none(overrides["competitive_moat_detail"].get("score_0_10")))

    cap_score = score_manual("mgmt_alloc_score", overrides)
    if overrides.get("mgmt_alloc_score") is None:
        from .capital_allocation import score_capital_allocation

        cap_score, cap_detail = score_capital_allocation(fundamentals, overrides)
        if cap_detail:
            fundamentals["capital_allocation_detail"] = cap_detail

    div_flag = overrides.get("divergence_signal")
    if div_flag is None:
        div_flag = detect_divergence_signal(
            current_price=_float_or_none(fundamentals.get("price")),
            fifty_two_week_high=_float_or_none(fundamentals.get("fifty_two_week_high")),
            price_history=fundamentals.get("price_history_series"),
            days_below_high=fundamentals.get("days_below_high"),
            fd_direction=str(overrides.get("fd_direction") or fundamentals.get("fd_direction") or "stable"),
            ticker=str(fundamentals.get("ticker") or ""),
        )

    return {
        "revenue_quality": score_revenue_quality(gross_m, fcf_m),
        "growth_trajectory": score_growth_trajectory(rev_g, rev_accel if isinstance(rev_accel, bool) else None),
        "margin_quality": score_margin_quality(business_type, rev_g, fcf_m, dist_cov, gross_m),
        "balance_sheet": bs_score,
        "roic_wacc_spread": score_roic_spread(roic, business_type),
        "gross_margin_trend": score_gross_margin_trend(margin_trend),
        "debt_maturity_risk": score_debt_maturity_risk(fundamentals, business_type, overrides),
        "ceo_quality": ceo_score,
        "mgmt_capital_allocation": cap_score,
        "competitive_moat": moat_score,
        "macro_tailwind": score_macro_tailwind(overrides),
        "divergence_signal": 2.0 if div_flag else 0.0,
        "deal_delay_risk": -1.0 if overrides.get("deal_delay_risk") or overrides.get("deal_delay_flag") else 0.0,
        "insider_ownership": _score_insider(insider_val),
        "reinvestment_runway": _score_reinvestment(reinvest_val),
    }


def build_fundamentals_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    info = raw.get("info", {})
    fast = raw.get("fast_info", {})
    errors = list(raw.get("errors", []))

    price = _float_or_none(
        _first_not_none(
            fast.get("last_price"),
            fast.get("lastPrice"),
            info.get("currentPrice"),
            info.get("regularMarketPrice"),
            info.get("previousClose"),
        )
    )
    market_cap = _float_or_none(_first_not_none(fast.get("market_cap"), fast.get("marketCap"), info.get("marketCap")))

    q_inc = raw.get("quarterly_income")
    q_bal = raw.get("quarterly_balance")
    q_cf = raw.get("quarterly_cashflow")
    shares = _float_or_none(
        _first_not_none(info.get("sharesOutstanding"), info.get("impliedSharesOutstanding"))
    )

    fundamentals: dict[str, Any] = {
        "ticker": raw.get("ticker"),
        "quote_type": info.get("quoteType"),
        "price": price,
        "market_cap": market_cap,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "payout_ratio": _float_or_none(info.get("payoutRatio")),
        "revenue_growth": _float_or_none(info.get("revenueGrowth")),
        "gross_margin": _float_or_none(info.get("grossMargins")),
    }

    revenue_ttm = _df_ttm_sum(q_inc, "Total Revenue", "Revenue", "Operating Revenue")
    gross_profit_ttm = _df_ttm_sum(q_inc, "Gross Profit")
    net_income_ttm = _df_ttm_sum(q_inc, "Net Income", "Net Income Common Stockholders")
    ebitda_ttm = _df_ttm_sum(q_inc, "EBITDA", "Normalized EBITDA")
    operating_cf_ttm = _df_ttm_sum(q_cf, "Operating Cash Flow", "Total Cash From Operating Activities")
    capex_ttm = _df_ttm_sum(q_cf, "Capital Expenditure")

    total_debt = _df_row(q_bal, "Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt")
    total_cash = _df_row(q_bal, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")

    if revenue_ttm and revenue_ttm > 0:
        info_revenue = _float_or_none(info.get("totalRevenue"))
        estimate = _float_or_none(info.get("revenueEstimate"))
        candidates = [v for v in (estimate, revenue_ttm, info_revenue) if v and v > 0]
        fwd_revenue = max(candidates) if candidates else revenue_ttm
        if info_revenue and info_revenue > 0:
            ratio = revenue_ttm / info_revenue
            # Statement TTM can be wrong currency/units for ADRs; trust info when far off.
            if ratio > 3.0 or ratio < 0.33:
                fwd_revenue = info_revenue
        fundamentals["fwd_revenue_stored"] = fwd_revenue
        if gross_profit_ttm is not None:
            fundamentals["gross_margin_computed"] = round(gross_profit_ttm / revenue_ttm, 6)

    if total_debt is not None or total_cash is not None:
        fundamentals["total_debt"] = total_debt
        fundamentals["cash_and_equivalents"] = total_cash
        fundamentals["net_debt_stored"] = (total_debt or 0.0) - (total_cash or 0.0)

    st_debt = _df_row(
        q_bal,
        "Current Debt",
        "Short Long Term Debt",
        "Current Portion of Long Term Debt",
    )
    if st_debt is not None and total_debt and total_debt > 0:
        fundamentals["short_term_debt_pct"] = round(st_debt / total_debt, 4)

    if operating_cf_ttm is not None and capex_ttm is not None:
        fundamentals["fcf_ttm"] = operating_cf_ttm + capex_ttm
        fundamentals["capex_ttm"] = capex_ttm
    else:
        fcf = _float_or_none(_first_not_none(info.get("freeCashflow"), info.get("freeCashFlow")))
        if not fcf or fcf <= 0:
            if q_cf is not None and "Free Cash Flow" in getattr(q_cf, "index", []):
                fcf = _df_ttm_sum(q_cf, "Free Cash Flow")
            if (not fcf or fcf <= 0) and operating_cf_ttm is not None and capex_ttm is not None:
                fcf = operating_cf_ttm - abs(capex_ttm)
        fundamentals["fcf_ttm"] = fcf

    fundamentals["revenue_ttm"] = revenue_ttm
    if revenue_ttm and revenue_ttm > 0:
        fundamentals["capex_ttm"] = fundamentals.get("capex_ttm") or capex_ttm

    fcf = fundamentals.get("fcf_ttm")
    rev_base = revenue_ttm or _float_or_none(info.get("totalRevenue"))
    if fcf is not None and rev_base and rev_base > 0:
        fundamentals["fcf_margin"] = round(fcf / rev_base, 6)

    # Prior-year FCF for FD vote 3
    if q_cf is not None:
        ocf_prior = _df_ttm_sum(q_cf, "Operating Cash Flow", "Total Cash From Operating Activities", periods=4)
        capex_prior = _df_ttm_sum(q_cf, "Capital Expenditure", periods=4)
        if ocf_prior is not None and capex_prior is not None and len(q_cf.columns) >= 8:
            try:
                ocf_row = q_cf.loc["Operating Cash Flow"] if "Operating Cash Flow" in q_cf.index else q_cf.loc["Total Cash From Operating Activities"]
                capex_row = q_cf.loc["Capital Expenditure"]
                # yfinance columns are newest-first; sort ascending so iloc[-4:] is the current
                # TTM quarter set and iloc[-8:-4] is the same four quarters one year prior.
                ocf_sorted = ocf_row.dropna().sort_index()
                capex_sorted = capex_row.dropna().sort_index()
                if len(ocf_sorted) >= 8:
                    fcf_prior = float(ocf_sorted.iloc[-8:-4].sum() + capex_sorted.iloc[-8:-4].sum())
                    fundamentals["fcf_prior_year"] = fcf_prior
                    if fcf is not None and fcf_prior and fcf_prior > 0:
                        fundamentals["fcf_growth_yoy"] = (fcf - fcf_prior) / abs(fcf_prior)
                    rev_prior = None
                    if q_inc is not None:
                        for label in ("Total Revenue", "Revenue", "Operating Revenue"):
                            if label in q_inc.index and len(q_inc.loc[label].dropna()) >= 8:
                                rev_prior = float(q_inc.loc[label].dropna().sort_index().iloc[-8:-4].sum())
                                break
                    if rev_prior and rev_prior > 0 and fcf_prior:
                        fundamentals["fcf_margin_prior"] = round(fcf_prior / rev_prior, 6)
            except Exception:
                pass

    if ebitda_ttm and ebitda_ttm > 0 and fundamentals.get("net_debt_stored") is not None:
        fundamentals["net_debt_ebitda"] = round(fundamentals["net_debt_stored"] / ebitda_ttm, 4)
    elif info.get("ebitda"):
        ebitda_info = _float_or_none(info.get("ebitda"))
        if ebitda_info and ebitda_info > 0 and fundamentals.get("net_debt_stored") is not None:
            fundamentals["net_debt_ebitda"] = round(fundamentals["net_debt_stored"] / ebitda_info, 4)

    fundamentals["eps_ttm"] = _float_or_none(info.get("trailingEps"))
    if not fundamentals["eps_ttm"] or fundamentals["eps_ttm"] <= 0:
        if net_income_ttm and shares and shares > 0:
            fundamentals["eps_ttm"] = net_income_ttm / shares
    fundamentals["eps_fwd"] = _float_or_none(info.get("forwardEps"))
    fundamentals["eps_estimate_current"] = fundamentals["eps_fwd"]

    shares_now = shares
    shares_prior = None
    if q_bal is not None:
        for label in ("Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"):
            if label not in getattr(q_bal, "index", []):
                continue
            sh_series = q_bal.loc[label].dropna().sort_index()
            if len(sh_series) >= 1:
                shares_now = float(sh_series.iloc[-1])
            if len(sh_series) >= 5:
                shares_prior = float(sh_series.iloc[-5])
            elif len(sh_series) >= 4:
                shares_prior = float(sh_series.iloc[0])
            break
    fundamentals["shares_outstanding_now"] = shares_now
    fundamentals["shares_outstanding_12m_ago"] = shares_prior
    if shares_now and shares_prior and shares_prior > 0:
        fundamentals["shares_outstanding_change_pct"] = round((shares_now - shares_prior) / shares_prior, 4)

    roe = _normalize_ratio(_float_or_none(info.get("returnOnEquity")))
    roa = _normalize_ratio(_float_or_none(info.get("returnOnAssets")))
    if roe is not None:
        fundamentals["roic_proxy"] = roe
    elif roa is not None:
        fundamentals["roic_proxy"] = roa
    elif q_bal is not None and net_income_ttm is not None:
        equity = _df_row(q_bal, "Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity")
        if equity and equity > 0:
            fundamentals["roic_proxy"] = net_income_ttm / equity

    div_rate = _float_or_none(_first_not_none(info.get("dividendRate"), info.get("trailingAnnualDividendRate")))
    fundamentals["annual_div_per_share_stored"] = div_rate
    if fcf is not None and div_rate is not None and shares and shares > 0:
        obligation = div_rate * shares
        if obligation > 0:
            fundamentals["distribution_coverage_ratio"] = round(fcf / obligation, 4)

    if q_inc is not None and not q_inc.empty:
        for label in ("Total Revenue", "Revenue", "Operating Revenue"):
            if label not in q_inc.index:
                continue
            # yfinance quarterly columns are newest-first; sort ascending so
            # iloc[-1] is always the latest quarter and iloc[-5] is the same
            # quarter one year prior, regardless of the raw column order.
            rev_sorted = q_inc.loc[label].dropna().sort_index()
            if len(rev_sorted) >= 5:
                latest = float(rev_sorted.iloc[-1])
                prior = float(rev_sorted.iloc[-5])
                if prior > 0:
                    fundamentals["revenue_growth_yoy"] = (latest - prior) / prior
            growth_rates = rev_sorted.pct_change(periods=4).dropna()
            if len(growth_rates) >= 3:
                last3 = growth_rates.tail(3).values
                fundamentals["revenue_accelerating"] = bool(last3[-1] > last3[-2] > last3[-3])
            if "Gross Profit" in q_inc.index and len(rev_sorted) >= 5:
                gp_sorted = q_inc.loc["Gross Profit"].dropna().sort_index()
                common_idx = rev_sorted.index.intersection(gp_sorted.index)
                if len(common_idx) >= 5:
                    rev_common = rev_sorted.loc[common_idx].sort_index()
                    gp_common = gp_sorted.loc[common_idx].sort_index()
                    gm_recent = float(gp_common.iloc[-1] / rev_common.iloc[-1]) if rev_common.iloc[-1] else None
                    gm_older = float(gp_common.iloc[-5] / rev_common.iloc[-5]) if rev_common.iloc[-5] else None
                    if gm_recent is not None and gm_older and gm_older > 0:
                        fundamentals["gross_margin_trend"] = (gm_recent - gm_older) / gm_older
            break

    held_pct = _float_or_none(info.get("heldPercentInsiders"))
    if held_pct is not None:
        # Match _score_insider / analyst overrides: percent on 0–100 scale (e.g. 6.5 not 0.065).
        fundamentals["insider_pct"] = held_pct * 100.0 if abs(held_pct) <= 1.0 else held_pct

    price_hist = raw.get("price_history")
    divs = raw.get("dividends")
    fundamentals["fifty_two_week_high"] = _float_or_none(
        _first_not_none(fast.get("year_high"), fast.get("fiftyDayHigh"), info.get("fiftyTwoWeekHigh"))
    )
    if isinstance(price_hist, pd.Series) and not price_hist.empty:
        fundamentals["price_history_series"] = price_hist
        if fundamentals.get("fifty_two_week_high") is None:
            fundamentals["fifty_two_week_high"] = float(price_hist.tail(252).max() if len(price_hist) >= 252 else price_hist.max())
        fundamentals.update(compute_dividend_yield_stats(pd.DataFrame({"Close": price_hist}), divs))
    elif fundamentals.get("fifty_two_week_high") is None:
        fundamentals["fifty_two_week_high"] = _float_or_none(info.get("fiftyTwoWeekHigh"))

    if isinstance(price_hist, pd.Series) and q_inc is not None:
        for label in ("Diluted EPS", "Basic EPS"):
            if label in q_inc.index:
                pe_bundle = compute_pe_history(price_hist, q_inc.loc[label])
                if pe_bundle.get("values"):
                    pe_bundle["meta"]["source"] = "yfinance"
                    ticker = fundamentals.get("ticker") or raw.get("ticker")
                    if pe_bundle["meta"].get("insufficient_20y") and ticker and is_us_ticker(ticker):
                        # SEC EDGAR first: free, unlimited, deeper (~15-19y vs FMP's
                        # free-tier 5y cap) — confirmed live 2026-07-24. FMP is only
                        # tried when SEC has genuinely nothing for this ticker (e.g.
                        # foreign private issuer filing 20-F, or not in SEC's CIK map).
                        sec_bundle = fetch_pe_history_sec(ticker, price_hist)
                        if sec_bundle and sec_bundle["meta"]["point_count"] > pe_bundle["meta"]["point_count"]:
                            pe_bundle = sec_bundle
                        if sec_bundle is None:
                            fmp_bundle = fetch_pe_history_fmp(ticker, target_years=PE_HISTORY_TARGET_YEARS)
                            if fmp_bundle and fmp_bundle["meta"]["point_count"] > pe_bundle["meta"]["point_count"]:
                                pe_bundle = fmp_bundle
                    fundamentals["pe_20y_array"] = pe_bundle["values"]
                    fundamentals["pe_history_meta"] = pe_bundle["meta"]
                break

    if fundamentals.get("revenue_growth_yoy") is not None:
        fundamentals["revenue_growth"] = fundamentals["revenue_growth_yoy"]

    fundamentals["fetch_errors"] = errors
    return fundamentals


def map_to_engine_fundamentals(enriched: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "quote_type",
        "price",
        "market_cap",
        "sector",
        "industry",
        "eps_ttm",
        "eps_fwd",
        "eps_estimate_current",
        "fcf_ttm",
        "fcf_prior_year",
        "fcf_growth_yoy",
        "fcf_margin",
        "fcf_margin_prior",
        "net_debt_stored",
        "fwd_revenue_stored",
        "revenue_ttm",
        "annual_div_per_share_stored",
        "revenue_growth",
        "gross_margin",
        "net_debt_ebitda",
        "distribution_coverage_ratio",
        "gross_margin_trend",
        "roic_proxy",
        "pe_20y_array",
        "pe_history_meta",
        "dividend_yield_5y_mean",
        "dividend_yield_5y_std",
        "revenue_accelerating",
        "insider_pct",
        "fifty_two_week_high",
        "shares_outstanding_change_pct",
        "shares_outstanding_now",
        "shares_outstanding_12m_ago",
        "days_below_high",
        "capital_allocation_detail",
    ]
    out = {k: enriched[k] for k in keys if k in enriched and enriched[k] is not None}
    if enriched.get("gross_margin_computed") is not None and "gross_margin" not in out:
        out["gross_margin"] = enriched["gross_margin_computed"]
    return out


def fetch_and_compute_fundamentals(ticker: str) -> dict[str, Any]:
    raw = fetch_yfinance_enriched(ticker)
    enriched = build_fundamentals_from_raw(raw)
    engine = map_to_engine_fundamentals(enriched)
    # Transient fields for divergence bootstrap (not persisted in JSON store)
    if enriched.get("price_history_series") is not None:
        engine["price_history_series"] = enriched["price_history_series"]
    if enriched.get("fifty_two_week_high") is not None:
        engine["fifty_two_week_high"] = enriched["fifty_two_week_high"]
    engine["fetch_errors"] = enriched.get("fetch_errors", [])
    raw_summary = {
        "info": raw.get("info", {}),
        "errors": list(raw.get("errors") or []),
        "quarterly_income": raw.get("quarterly_income"),
        "quarterly_balance": raw.get("quarterly_balance"),
        "quarterly_cashflow": raw.get("quarterly_cashflow"),
    }
    return {"info": raw.get("info", {}), "fundamentals": engine, "raw": raw_summary}
