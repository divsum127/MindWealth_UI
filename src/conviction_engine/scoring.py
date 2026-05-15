"""Scoring and verdict rules for Conviction Engine v5."""

from __future__ import annotations

from typing import Any

from .models import BusinessType, FsClass

NON_EQUITY_TYPES = {"ETF", "INDEX", "CURRENCY", "CRYPTOCURRENCY", "FUTURE", "MUTUALFUND"}
COMMON_ETFS = {
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "EEM",
    "ASHR",
    "FXI",
    "GLD",
    "GDX",
    "SOXX",
    "XLU",
    "XLY",
    "XLV",
    "XLF",
    "XLE",
    "VGT",
    "XIU.TO",
}

EV_REV_TIERS = {
    BusinessType.SAAS.value: ([3, 5, 8, 12], 4),
    BusinessType.COMPOUNDER.value: ([1.5, 3, 6, 8], 3),
    BusinessType.INCOME.value: ([4, 6, 8, 10], 6),
    BusinessType.CYCLICAL.value: ([1, 2.5, 4, 5], None),
    BusinessType.UNKNOWN.value: ([2, 4, 6, 8], None),
}

OEY_STRONG = {
    BusinessType.SAAS.value: 0.05,
    BusinessType.COMPOUNDER.value: 0.04,
    BusinessType.CYCLICAL.value: 0.04,
    BusinessType.INCOME.value: 0.03,
    BusinessType.UNKNOWN.value: 0.04,
}


def infer_asset_type(ticker: str, quote_type: str | None = None) -> tuple[str, str | None]:
    if quote_type:
        normalized = str(quote_type).upper()
        if normalized in NON_EQUITY_TYPES:
            return normalized, f"quoteType={normalized}"
        if normalized == "EQUITY":
            return "EQUITY", None

    symbol = ticker.upper()
    if symbol.startswith("^"):
        return "INDEX", "symbol starts with index marker"
    if symbol.endswith("=X"):
        return "CURRENCY", "symbol is an FX pair"
    if symbol.endswith("-USD") or symbol.endswith("-USDT"):
        return "CRYPTOCURRENCY", "symbol is crypto-like"
    if symbol in COMMON_ETFS:
        return "ETF", "symbol is a known ETF/fund"
    return "EQUITY", None


def is_equity_asset(record: dict[str, Any], ticker: str) -> tuple[bool, str, str | None]:
    asset_type = str(record.get("asset_type") or "").upper()
    quote_type = str(record.get("quote_type") or "") or None
    inferred, reason = infer_asset_type(ticker, quote_type if quote_type != "NONE" else None)
    final_type = asset_type if asset_type and asset_type != "UNKNOWN" else inferred
    if final_type in NON_EQUITY_TYPES:
        return False, final_type, reason or f"asset_type={final_type}"
    return True, final_type or "EQUITY", None


def detect_business_type(info: dict[str, Any] | None = None, overrides: dict[str, Any] | None = None) -> tuple[str, str]:
    overrides = overrides or {}
    info = info or {}
    manual_type = overrides.get("business_type")
    if manual_type:
        return str(manual_type).lower(), "manual"

    quote_type = str(info.get("quoteType") or info.get("quote_type") or "").upper()
    if quote_type and quote_type != "EQUITY":
        return BusinessType.UNKNOWN.value, "auto"

    sector = str(info.get("sector") or "").lower()
    industry = str(info.get("industry") or "").lower()
    payout = _float_or_none(info.get("payoutRatio"))
    dividend_yield = _normalise_dividend_yield(info.get("dividendYield"))

    income_tokens = ("utility", "telecom", "pipeline", "reit", "regulated utility", "regulated")
    cyclical_tokens = ("energy", "materials", "mining", "metal", "oil", "gas", "commodity")
    saas_tokens = ("software", "saas", "application", "cloud")

    if any(token in industry or token in sector for token in income_tokens):
        return BusinessType.INCOME.value, "auto"
    if "infrastructure" in industry and "software" not in industry:
        return BusinessType.INCOME.value, "auto"
    if any(token in industry or token in sector for token in cyclical_tokens):
        return BusinessType.CYCLICAL.value, "auto"
    if any(token in industry or token in sector for token in saas_tokens):
        return BusinessType.SAAS.value, "auto"
    if dividend_yield and dividend_yield >= 0.025 and (payout is None or payout >= 0.45):
        return BusinessType.INCOME.value, "auto"
    return BusinessType.COMPOUNDER.value, "auto"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_dividend_yield(value: Any) -> float | None:
    dividend_yield = _float_or_none(value)
    if dividend_yield is None:
        return None
    # yfinance can provide either decimals (0.073) or percent-like values (7.3).
    # Values above 25% are more likely percent-form for normal public equities.
    if dividend_yield > 0.25:
        return dividend_yield / 100.0
    return dividend_yield


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def compute_bq_components(inputs: dict[str, Any] | None = None, overrides: dict[str, Any] | None = None) -> dict[str, float]:
    data = inputs or {}
    overrides = overrides or {}
    if isinstance(overrides.get("bq_components"), dict):
        return {str(k): float(v) for k, v in overrides["bq_components"].items()}

    revenue_growth = _float_or_none(data.get("revenue_growth")) or _float_or_none(overrides.get("revenue_growth"))
    fcf_margin = _float_or_none(data.get("fcf_margin")) or _float_or_none(overrides.get("fcf_margin"))
    gross_margin = _float_or_none(data.get("gross_margin")) or _float_or_none(overrides.get("gross_margin"))
    net_debt_ebitda = _float_or_none(data.get("net_debt_ebitda")) or _float_or_none(overrides.get("net_debt_ebitda"))
    roic_wacc_spread = _float_or_none(data.get("roic_wacc_spread")) or _float_or_none(overrides.get("roic_wacc_spread"))
    distribution_coverage = _float_or_none(data.get("distribution_coverage_ratio")) or _float_or_none(
        overrides.get("distribution_coverage_ratio")
    )

    def score_manual(name: str, low: float = 4, high: float = 7) -> float:
        value = _float_or_none(overrides.get(name))
        if value is None:
            return 0.0
        if value >= high:
            return 2.0
        if value >= low:
            return 0.0
        return -1.0

    components = {
        "revenue_quality": 1.0 if (gross_margin or 0) >= 0.35 else 0.0,
        "growth_trajectory": 2.0 if (revenue_growth or 0) >= 0.15 else (1.0 if (revenue_growth or 0) >= 0.05 else 0.0),
        "margin_quality": 0.0,
        "balance_sheet": -1.0 if net_debt_ebitda and net_debt_ebitda >= 5 else (1.0 if net_debt_ebitda is not None and net_debt_ebitda <= 1.5 else 0.0),
        "roic_wacc_spread": 2.0 if (roic_wacc_spread or 0) >= 0.03 else (1.0 if (roic_wacc_spread or 0) > 0 else 0.0),
        "gross_margin_trend": float(overrides.get("gross_margin_trend", 0.0) or 0.0),
        "debt_maturity_risk": float(overrides.get("debt_maturity_risk", 0.0) or 0.0),
        "ceo_quality": score_manual("ceo_quality_score"),
        "mgmt_capital_allocation": score_manual("mgmt_alloc_score"),
        "competitive_moat": score_manual("competitive_moat_score"),
        "macro_tailwind": float(overrides.get("macro_tailwind", 0.0) or 0.0),
        "divergence_signal": 2.0 if overrides.get("divergence_signal") else 0.0,
        "deal_delay_risk": -1.0 if overrides.get("deal_delay_risk") else 0.0,
        "insider_ownership": _score_insider(overrides.get("insider_ownership")),
        "reinvestment_runway": _score_reinvestment(overrides.get("reinvestment_runway")),
    }

    rule_of_40 = ((revenue_growth or 0) + (fcf_margin or 0)) * 100
    if distribution_coverage is not None:
        components["margin_quality"] = 2.0 if distribution_coverage > 2 else (0.0 if distribution_coverage >= 1.2 else -1.0)
    elif rule_of_40 >= 40:
        components["margin_quality"] = 2.0
    elif rule_of_40 >= 20:
        components["margin_quality"] = 1.0
    elif fcf_margin is not None and fcf_margin < 0:
        components["margin_quality"] = -1.0

    return components


def _score_insider(value: Any) -> float:
    pct = _float_or_none(value)
    if pct is None:
        return 0.0
    if pct > 15:
        return 2.0
    if pct < 1:
        return -1.0
    return 0.0


def _score_reinvestment(value: Any) -> float:
    multiple = _float_or_none(value)
    if multiple is None:
        return 0.0
    if multiple >= 5:
        return 1.0
    if multiple < 3:
        return -1.0
    return 0.0


def calculate_bq_raw(components: dict[str, float]) -> float:
    return round(sum(float(value) for value in components.values()), 2)


def calculate_valuation_tax(record: dict[str, Any]) -> float:
    business_type = str(record.get("business_type") or BusinessType.UNKNOWN.value)
    ev_rev = _float_or_none(record.get("ev_fwd_rev"))
    pe_pct = _float_or_none(record.get("pe_percentile_20y"))
    oey = _float_or_none(record.get("owner_earnings_yield"))

    tax = 0.0
    tiers, floor_trigger = EV_REV_TIERS.get(business_type, EV_REV_TIERS[BusinessType.UNKNOWN.value])
    if ev_rev is not None:
        tier_tax = 0.0
        for idx, threshold in enumerate(tiers, start=1):
            if ev_rev >= threshold:
                tier_tax = -float(idx)
        tax += tier_tax
        # Apply extreme valuation floor only at the top EV/rev tier (not mid-tier names).
        if ev_rev >= tiers[-1]:
            tax = min(tax, -5.0)
        if business_type == BusinessType.INCOME.value and ev_rev < tiers[0]:
            tax += 1.0

    if pe_pct is not None:
        if pe_pct >= 85:
            tax -= 3.0
        elif pe_pct >= 70:
            tax -= 2.0
        elif pe_pct >= 55:
            tax -= 1.0

    if oey is not None and oey < 0.01:
        tax -= 2.0

    return round(max(-5.0, min(0.0, tax)), 2)


def calculate_fs_score(record: dict[str, Any]) -> float:
    business_type = str(record.get("business_type") or BusinessType.UNKNOWN.value)
    bq_raw = _float_or_none(record.get("bq_raw")) or 0.0
    base = _float_or_none(record.get("fs_quality_base"))
    score = base if base is not None else 50 + (bq_raw * 2.5)

    oey = _float_or_none(record.get("owner_earnings_yield"))
    pe_pct = _float_or_none(record.get("pe_percentile_20y"))
    ev_rev = _float_or_none(record.get("ev_fwd_rev"))

    if oey is not None:
        if oey >= OEY_STRONG.get(business_type, 0.04):
            score += 5
        elif oey < 0.01:
            score -= 8

    if pe_pct is not None:
        if pe_pct <= 30:
            score += 5
        elif pe_pct >= 80:
            score -= 6

    if ev_rev is not None:
        tiers, _ = EV_REV_TIERS.get(business_type, EV_REV_TIERS[BusinessType.UNKNOWN.value])
        if ev_rev >= tiers[-1]:
            score -= 8
        elif ev_rev < tiers[0]:
            score += 3

    return round(clamp(score, 0, 100), 2)


def classify_fs(score: float | None) -> str:
    score = score if score is not None else 50
    if score >= 75:
        return FsClass.STRONG.value
    if score >= 55:
        return FsClass.MODERATE_HIGH.value
    if score >= 40:
        return FsClass.MODERATE.value
    if score >= 25:
        return FsClass.MODERATE_LOW.value
    return FsClass.WEAK.value


def apply_fs_cap(conviction_score: float, fs_class: str, signal_timeframe: str) -> tuple[float, str | None]:
    if signal_timeframe == "long":
        if fs_class == FsClass.WEAK.value:
            return min(conviction_score, 1.0), "FS weak capped long signal at +1"
        if fs_class == FsClass.MODERATE_LOW.value:
            return min(conviction_score, 4.0), "FS moderate_low capped long signal at +4"
    else:
        if fs_class == FsClass.WEAK.value:
            return min(conviction_score, 2.0), "FS weak capped short signal at +2"
    return conviction_score, None


def market_yield_threshold(ticker: str) -> float:
    symbol = ticker.upper()
    if symbol.endswith(".NZ"):
        return 0.12
    if symbol.endswith(".AX"):
        return 0.10
    if symbol.endswith(".TO"):
        return 0.07
    if symbol.endswith(".L"):
        return 0.09
    return 0.06


def is_yield_trap(record: dict[str, Any], ticker: str) -> bool:
    zscore = _float_or_none(record.get("dividend_yield_zscore"))
    current_yield = _float_or_none(record.get("dividend_yield_current"))
    if zscore is None or current_yield is None:
        return bool(record.get("yield_trap_warning", False))
    return zscore > 1.5 and current_yield > market_yield_threshold(ticker)


def verdict_for_buy(score: float, fd_direction: str | None = None, yield_trap: bool = False) -> tuple[str, float]:
    if yield_trap:
        return "CANCEL BUY", 0.0
    fd = str(fd_direction or "stable").lower()
    if score >= 8:
        return "MAX CONVICTION", 100.0
    if score >= 5:
        if fd == "positive":
            return "TACTICAL BUY", 85.0
        if fd == "negative":
            return "TACTICAL BUY", 60.0
        return "TACTICAL BUY", 75.0
    if score >= 2:
        if fd == "positive":
            return "REDUCED BUY", 50.0
        if fd == "negative":
            return "REDUCED BUY", 25.0
        return "REDUCED BUY", 40.0
    return "CANCEL BUY", 0.0


def verdict_for_sell(score: float, signal_timeframe: str, yield_trap: bool = False) -> tuple[str, float]:
    if yield_trap:
        return "HARD EXIT", 0.0
    if signal_timeframe == "short":
        if score >= 8:
            return "PAUSE SELL", 0.0
        if score >= 5:
            return "PARTIAL EXIT", 0.0
        if score >= 2:
            return "FULL EXIT", 0.0
        return "HARD EXIT", 0.0
    if score >= 8:
        return "PAUSE SELL", 70.0
    if score >= 5:
        return "PARTIAL EXIT", 50.0
    if score >= 2:
        return "FULL EXIT", 0.0
    return "HARD EXIT", 0.0
