"""Scoring and verdict rules for Conviction Engine v6."""

from __future__ import annotations

from typing import Any

from .models import KNOWN_BUSINESS_TYPES, BusinessType, FsClass

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
    # Bond / treasury / broad market ETFs used in VT book
    "TLT",
    "IEF",
    "SHY",
    "BND",
    "AGG",
    "LQD",
    "HYG",
    "MCHI",
    "EFA",
    "EWJ",
    "EWZ",
    "INDA",
    "VEA",
    "VTI",
    "VOO",
}

# EV/forward-revenue tier boundaries per business type, used for the `entry_multiple`
# valuation-tax component and the FS-score EV/Revenue slice row. `bank` is intentionally
# absent — its entry_multiple/FS-valuation row is the P/TBV-vs-ROE model instead (see
# bank_valuation.py). `high_margin_hardware` is intentionally absent too — its driver is
# EV/forward-EBITDA (EV_EBITDA_TIERS below), not raw EV/Revenue (item 4/Section 5.5).
#
# v2 (30 July 2026 answers) fix: the old per-type `min_penalty_trigger` second tuple
# element is gone — the -5 floor is now a universal 4x-forward-revenue rule (see
# `_apply_universal_floor_and_fragility`), not type-specific.
EV_REV_TIERS = {
    BusinessType.SAAS.value: [3, 5, 8, 12],
    BusinessType.COMPOUNDER.value: [1.5, 3, 6, 8],
    BusinessType.INCOME.value: [4, 6, 8, 10],
    BusinessType.CYCLICAL.value: [1, 2.5, 4, 5],
    BusinessType.UNKNOWN.value: [2, 4, 6, 8],
}

# EV/forward-EBITDA tier boundaries for `high_margin_hardware` (item 4, Section 5.5):
# margin-normalized driver instead of raw EV/Revenue, since a high multiple here is
# backed by current profit rather than a pure growth story.
EV_EBITDA_TIERS: list[float] = [10, 15, 20, 25]

UNIVERSAL_FLOOR_EV_REV_TRIGGER = 4.0  # any stock >=4x forward revenue floors entry_multiple at -5
UNIVERSAL_FLOOR_VALUE = -5.0
GROWTH_FRAGILITY_EV_REV_TRIGGER = 4.0  # Section 5.3: EV/fwd rev >=4x AND growth >=15% -> -2.0
GROWTH_FRAGILITY_GROWTH_TRIGGER = 0.15
GROWTH_FRAGILITY_PENALTY = -2.0

OEY_STRONG = {
    BusinessType.SAAS.value: 0.05,
    BusinessType.COMPOUNDER.value: 0.04,
    BusinessType.CYCLICAL.value: 0.04,
    BusinessType.INCOME.value: 0.03,
    BusinessType.BANK.value: 0.04,
    BusinessType.HIGH_MARGIN_HARDWARE.value: 0.04,
    BusinessType.UNKNOWN.value: 0.04,
}

# Raw sector/industry tokens for semiconductor/hardware names — used to key the G2
# source-hygiene fix (item 6) off the *sector*, not the `high_margin_hardware` bucket,
# so a 25%-margin chip company still gets Gartner/patent sourcing instead of G2.
HARDWARE_SECTOR_TOKENS = (
    "semiconductor",
    "hardware",
    "electronic equipment",
    "computer hardware",
    "communication equipment",
)

# Bank detection tokens (item 1): sector must be Financial Services AND industry must
# reference a banking business line (commercial/regional/diversified banks) — this
# excludes insurers, asset managers, and capital-markets firms that also sit in
# "Financial Services" but aren't banks.
BANK_SECTOR_TOKEN = "financial services"
BANK_INDUSTRY_TOKENS = ("bank", "banks")
INSURER_INDUSTRY_TOKENS = ("insurance",)

HIGH_MARGIN_HARDWARE_NET_MARGIN_THRESHOLD = 0.40

# ── Margin-normalised EV/Revenue (Rohit 1 Sep, E2 / 28 July note §5.7) ────────────
# "On the threshold itself — don't set one. A cliff at 50% means 49.9% and 50.1% get
# different treatment for no reason. Use the continuous version already in Section 5.7:
# margin-normalised EV/Revenue, raw EV/Rev divided by net margin over 20%. Every name,
# no bucket gate."
#
# The shipped threshold was 40%, not the 50% the note argued against, but the objection
# is the same either way: it is a cliff, and it also decides the tie-break question for
# names spanning two buckets. The continuous form removes both problems — there is no
# bucket to be on the wrong side of.
MARGIN_NORMALISATION_BASE = 0.20


def margin_normalised_ev_rev(ev_rev: float | None, net_margin: float | None) -> float | None:
    """Raw EV/Revenue divided by net margin expressed over a 20% base.

    A 40%-margin name on 8x revenue normalises to 4x — the same as a 20%-margin name on
    4x, which is the point: the multiple is judged against the profitability backing it
    rather than against a bucket the name was sorted into. Returns ``None`` when either
    input is missing, and leaves ``ev_rev`` untouched for a loss-making name, where the
    normalisation has no meaning.
    """
    if ev_rev is None:
        return None
    if net_margin is None or net_margin <= 0:
        return ev_rev
    return round(ev_rev / (net_margin / MARGIN_NORMALISATION_BASE), 4)


def is_hardware_or_semiconductor_sector(info: dict[str, Any] | None) -> bool:
    """Raw sector/industry token check (item 6) — independent of the 40%-margin
    `high_margin_hardware` business-type test, so source-hygiene fixes (G2 exclusion)
    apply to every hardware/semiconductor name, not only the high-margin ones."""
    info = info or {}
    sector = str(info.get("sector") or "").lower()
    industry = str(info.get("industry") or "").lower()
    return any(token in industry or token in sector for token in HARDWARE_SECTOR_TOKENS)


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

    # `coverage_incomplete` hard gate (item 5): insurers and genuinely unresolved
    # sector data must land on `unknown`, not silently fall through to `compounder`
    # like every other unmatched name does. "Deep value" has no sector-based
    # detection rule from Rohit — only reachable via an explicit manual override
    # tag outside the 6 known types (see conviction_fixes_decisions.md).
    if any(token in industry or token in sector for token in INSURER_INDUSTRY_TOKENS):
        return BusinessType.UNKNOWN.value, "auto_coverage_incomplete"
    if not sector and not industry:
        return BusinessType.UNKNOWN.value, "auto_coverage_incomplete"

    income_tokens = ("utility", "telecom", "pipeline", "reit", "regulated utility", "regulated")
    cyclical_tokens = ("energy", "materials", "mining", "metal", "oil", "gas", "commodity")
    saas_tokens = ("software", "saas", "application", "cloud")

    if any(token in industry or token in sector for token in income_tokens):
        return BusinessType.INCOME.value, "auto"
    if "infrastructure" in industry and "software" not in industry:
        return BusinessType.INCOME.value, "auto"

    if BANK_SECTOR_TOKEN in sector and any(token in industry for token in BANK_INDUSTRY_TOKENS):
        return BusinessType.BANK.value, "auto"

    if is_hardware_or_semiconductor_sector(info):
        net_margin = _float_or_none(info.get("profitMargins"))
        if net_margin is not None and net_margin >= HIGH_MARGIN_HARDWARE_NET_MARGIN_THRESHOLD:
            return BusinessType.HIGH_MARGIN_HARDWARE.value, "auto"
        # Fails the 40% margin test -> stays cyclical (item 1): source-hygiene fix
        # (item 6) still applies via `is_hardware_or_semiconductor_sector()`, but
        # WACC/valuation tiers/margin_quality stay on standard cyclical defaults.
        return BusinessType.CYCLICAL.value, "auto"

    if any(token in industry or token in sector for token in cyclical_tokens):
        return BusinessType.CYCLICAL.value, "auto"
    if any(token in industry or token in sector for token in saas_tokens):
        return BusinessType.SAAS.value, "auto"
    if dividend_yield and dividend_yield >= 0.025 and (payout is None or payout >= 0.45):
        return BusinessType.INCOME.value, "auto"
    return BusinessType.COMPOUNDER.value, "auto"


def is_coverage_incomplete(business_type: str | None) -> bool:
    """True when `business_type` isn't one of the 6 calibrated types (item 5)."""
    return str(business_type or "").lower() not in KNOWN_BUSINESS_TYPES


# ── Framework coverage (Rohit 1 Sep, section F / 28 July note §12) ─────────────────
# A business type with no purpose-built valuation module does not fail loudly. It falls
# through to the generic EV/Revenue path and produces a confident, wrong number. Proven
# on NVDA, and again on MCY and SPK: both are capital-intensive names whose economics run
# on EV/EBITDA and FCF yield, but they route to EV/Revenue tiers they sit far below, so
# the valuation tax contributes almost nothing and the score reads as conviction.
#
# `coverage_incomplete` does not catch this, because these names ARE typed — they are
# `income` and `compounder`, which are "known". The distinction that matters is not
# whether we recognised the business, it is whether we built a model for it.
#
# Only three types have a purpose-built valuation slice today: banks (P/TBV vs ROE),
# high-margin hardware (EV/EBITDA), and SaaS (the EV/Revenue tiers were calibrated on
# SaaS multiples). Everything else borrows SaaS-shaped machinery.
MODELLED_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        BusinessType.BANK.value,
        BusinessType.HIGH_MARGIN_HARDWARE.value,
        BusinessType.SAAS.value,
    }
)

# Conviction ceiling applied where no module exists. Not a penalty — the July rule is
# that missing data scores neutral and never negative — but a cap, so an unmodelled name
# cannot present as a high-conviction buy on machinery that was never built for it.
UNMODELLED_CONVICTION_CAP = 4.0


def has_framework_coverage(business_type: str | None) -> bool:
    """True when this business type has a purpose-built valuation module."""
    return str(business_type or "").lower() in MODELLED_BUSINESS_TYPES


def apply_framework_coverage_cap(
    conviction_score: float,
    business_type: str | None,
) -> tuple[float, str | None]:
    """Cap conviction where the business type has no built module.

    Returns ``(score, note)``; ``note`` is None when no cap applied.
    """
    if has_framework_coverage(business_type):
        return conviction_score, None
    if conviction_score <= UNMODELLED_CONVICTION_CAP:
        return conviction_score, None
    label = str(business_type or "unknown")
    return (
        UNMODELLED_CONVICTION_CAP,
        f"Framework coverage: no valuation module built for business_type='{label}'; "
        f"conviction capped at +{UNMODELLED_CONVICTION_CAP:.0f} (scored on generic "
        "EV/Revenue machinery calibrated for other business types)",
    )


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

    components = {
        "revenue_quality": 1.0 if (gross_margin or 0) >= 0.35 else 0.0,
        "growth_trajectory": 2.0 if (revenue_growth or 0) >= 0.15 else (1.0 if (revenue_growth or 0) >= 0.05 else 0.0),
        "margin_quality": 0.0,
        "balance_sheet": -1.0 if net_debt_ebitda and net_debt_ebitda >= 5 else (1.0 if net_debt_ebitda is not None and net_debt_ebitda <= 1.5 else 0.0),
        "roic_wacc_spread": 2.0 if (roic_wacc_spread or 0) >= 0.03 else (1.0 if (roic_wacc_spread or 0) > 0 else 0.0),
        "gross_margin_trend": float(overrides.get("gross_margin_trend", 0.0) or 0.0),
        "debt_maturity_risk": float(overrides.get("debt_maturity_risk", 0.0) or 0.0),
        "ceo_quality": score_manual("ceo_quality_score", overrides),
        "mgmt_capital_allocation": score_manual("mgmt_alloc_score", overrides),
        "competitive_moat": score_manual("competitive_moat_score", overrides),
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
    """TAM/Revenue ratio: >10x → +1, 3–10x → 0, <3x → -1."""
    multiple = _float_or_none(value)
    if multiple is None:
        return 0.0
    if multiple > 10:
        return 1.0
    if multiple < 3:
        return -1.0
    return 0.0


def calculate_bq_raw(components: dict[str, float]) -> float:
    return round(sum(float(value) for value in components.values()), 2)


def score_manual(name: str, overrides: dict[str, Any], *, low: float = 3.0, mid: float = 5.0, high: float = 8.0) -> float:
    """Map analyst 0–10 override to BQ points: 8-10→+2, 5-7→+1, 3-4→0, 0-2→-1."""
    value = _float_or_none(overrides.get(name))
    if value is None:
        return 0.0
    if value >= high:
        return 2.0
    if value >= mid:
        return 1.0
    if value >= low:
        return 0.0
    return -1.0


def _tiered_tax(value: float, tiers: list[float]) -> float:
    tax = 0.0
    for idx, threshold in enumerate(tiers, start=1):
        if value >= threshold:
            tax = -float(idx)
    return tax


def calculate_valuation_tax_components(record: dict[str, Any]) -> dict[str, float]:
    """Per-component valuation tax (v6). Sum is capped to [-10, 0].

    v2 (30 July 2026 answers) fixes applied here (item 2):
    - The -5 floor is now universal (any name >=4x forward revenue), not a
      per-type trigger list — except `high_margin_hardware`, fully exempt.
    - `growth_multiple_fragility` now fires on EV/fwd rev >=4x AND growth >=15%
      (fast growth priced in -> deceleration is the risk), not on the old
      "top-tier multiple AND slow growth" condition.
    `bank` and `high_margin_hardware` substitute their own entry_multiple driver
    (P/TBV-vs-ROE, EV/forward-EBITDA respectively) instead of raw EV/Revenue.
    """
    business_type = str(record.get("business_type") or BusinessType.UNKNOWN.value)
    ev_rev = _float_or_none(record.get("ev_fwd_rev"))
    pe_pct = _float_or_none(record.get("pe_percentile_20y"))
    oey = _float_or_none(record.get("owner_earnings_yield"))
    revenue_growth = _float_or_none(record.get("revenue_growth"))
    pe_insufficient = bool(record.get("pe_history_insufficient"))

    components: dict[str, float] = {
        "entry_multiple": 0.0,
        "pe_hist_percentile": 0.0,
        "growth_multiple_fragility": 0.0,
        "business_type_relief": 0.0,
        "deal_delay_signal": 0.0,
        "market_regime_beta": 0.0,
        "oey_penalty": 0.0,
    }

    if business_type == BusinessType.BANK.value:
        from .bank_valuation import bank_ptbv_valuation_tax

        components["entry_multiple"], _ = bank_ptbv_valuation_tax(record)
    elif business_type == BusinessType.HIGH_MARGIN_HARDWARE.value:
        ev_ebitda = _float_or_none(record.get("ev_fwd_ebitda"))
        if ev_ebitda is not None:
            components["entry_multiple"] = _tiered_tax(ev_ebitda, EV_EBITDA_TIERS)
        # Fully exempt from the universal -5 floor (item 4/Section 5.5) — a high
        # EV/EBITDA multiple here is backed by current profit, not a growth story.
    else:
        tiers = EV_REV_TIERS.get(business_type, EV_REV_TIERS[BusinessType.UNKNOWN.value])
        # Margin-normalised, so the multiple is judged against the profitability backing
        # it rather than against the bucket the name landed in (Rohit 1 Sep, E2). The raw
        # figure is kept alongside, since that is what a reader recognises.
        net_margin = _float_or_none(record.get("net_margin"))
        ev_rev_normalised = margin_normalised_ev_rev(ev_rev, net_margin)
        record["ev_fwd_rev_margin_normalised"] = ev_rev_normalised
        ev_rev_for_tax = ev_rev_normalised if ev_rev_normalised is not None else ev_rev
        if ev_rev_for_tax is not None:
            components["entry_multiple"] = _tiered_tax(ev_rev_for_tax, tiers)
            if business_type == BusinessType.INCOME.value and ev_rev_for_tax < tiers[0]:
                components["business_type_relief"] = 1.0
        if ev_rev is not None and ev_rev >= UNIVERSAL_FLOOR_EV_REV_TRIGGER:
            components["entry_multiple"] = min(components["entry_multiple"], UNIVERSAL_FLOOR_VALUE)

    if pe_pct is not None and not pe_insufficient:
        if pe_pct >= 85:
            components["pe_hist_percentile"] = -3.0
        elif pe_pct >= 70:
            components["pe_hist_percentile"] = -2.0
        elif pe_pct >= 55:
            components["pe_hist_percentile"] = -1.0

    # Universal growth-multiple-fragility (item 2): applies regardless of which
    # entry_multiple driver was used above, since it's evaluated on EV/fwd revenue
    # specifically, not on whatever drove entry_multiple.
    if (
        ev_rev is not None
        and ev_rev >= GROWTH_FRAGILITY_EV_REV_TRIGGER
        and revenue_growth is not None
        and revenue_growth >= GROWTH_FRAGILITY_GROWTH_TRIGGER
    ):
        components["growth_multiple_fragility"] = GROWTH_FRAGILITY_PENALTY

    if oey is not None and oey < 0.01:
        components["oey_penalty"] = -2.0

    overrides = record.get("manual_overrides") or {}
    # Deal delay is counted in BQ as well. The tax leg exists because a delayed deal
    # signals slowing growth and a hard multiple re-rate — but that risk only exists if
    # there is a growth premium in the price to lose. SPK trades at 1.36x revenue, so
    # taxing it there punished the same fact twice for nothing. Gated at EV/forward
    # revenue of 4x and above; below that, deal delay counts once, in BQ.
    # (Rohit 1 Sep, C5. KXS at 5x is unaffected; SPK's tax goes from -3 to -1.)
    if overrides.get("deal_delay_flag") or overrides.get("deal_delay_risk"):
        ev_rev_for_gate = _float_or_none(record.get("ev_fwd_rev"))
        if ev_rev_for_gate is not None and ev_rev_for_gate >= DEAL_DELAY_TAX_EV_REV_FLOOR:
            components["deal_delay_signal"] = -1.0
        else:
            # Recorded so the absence is visible rather than looking like no signal.
            record["deal_delay_tax_gated"] = True
    regime = _float_or_none(overrides.get("market_regime_beta"))
    if regime is not None and regime > 1.2:
        components["market_regime_beta"] = -1.0

    return components


def calculate_valuation_tax(record: dict[str, Any]) -> float:
    components = calculate_valuation_tax_components(record)
    total = sum(components.values())
    return round(max(-10.0, min(0.0, total)), 2)


def valuation_tax_breakdown(record: dict[str, Any]) -> dict[str, Any]:
    components = calculate_valuation_tax_components(record)
    out: dict[str, Any] = {
        "components": {k: round(v, 2) for k, v in components.items()},
        "total": calculate_valuation_tax(record),
    }
    business_type = str(record.get("business_type") or BusinessType.UNKNOWN.value)
    if business_type == BusinessType.BANK.value:
        from .bank_valuation import bank_ptbv_valuation_tax

        _, ptbv_detail = bank_ptbv_valuation_tax(record)
        out["bank_ptbv_detail"] = ptbv_detail
    elif business_type == BusinessType.HIGH_MARGIN_HARDWARE.value:
        out["ev_fwd_ebitda"] = record.get("ev_fwd_ebitda")
    return out


# FS-score daily valuation slice (item 13, fully specced 2026-07 follow-up) — replaces
# the old ad hoc thresholds above. Symmetric, not penalty-only: cheap adds, expensive
# subtracts (unlike the always-<=0 valuation tax). ~±10 per input, ~±30 overall — enough
# to move one fs_class bracket, not enough to erase the BQ half of the score.
OEY_EXPENSIVE = 0.01  # flat across types; reuses the existing valuation-tax oey_penalty threshold


def _fs_pe_percentile_points(pe_pct: float | None) -> float:
    """Self-calibrating, one table for every business type."""
    if pe_pct is None:
        return 0.0
    if pe_pct < 20:
        return 10.0
    if pe_pct < 40:
        return 5.0
    if pe_pct < 60:
        return 0.0
    if pe_pct < 80:
        return -5.0
    return -10.0


def _fs_oey_points(oey: float | None, business_type: str) -> float:
    """Anchored to the existing per-type OEY_STRONG thresholds."""
    if oey is None:
        return 0.0
    strong = OEY_STRONG.get(business_type, OEY_STRONG[BusinessType.UNKNOWN.value])
    expensive = OEY_EXPENSIVE
    if oey >= strong * 1.5:
        return 10.0
    if oey >= strong:
        return 5.0
    if oey > expensive:
        return 0.0
    if oey > expensive * 0.5:
        return -5.0
    return -10.0


def _fs_tiered_points(value: float | None, tiers: list[float]) -> float:
    """Reuses the same 4-boundary tier lists as the valuation tax (EV_REV_TIERS /
    EV_EBITDA_TIERS), but symmetric: below tier[0] adds instead of just "no penalty"."""
    if value is None or not tiers:
        return 0.0
    if value < tiers[0]:
        return 10.0
    if value < tiers[1]:
        return 5.0
    if value < tiers[2]:
        return 0.0
    if value < tiers[3]:
        return -5.0
    return -10.0


def fs_score_breakdown(record: dict[str, Any]) -> dict[str, Any]:
    """Row-level breakdown of the FS-score daily valuation slice, for the Engine
    Layers "FS Cap" click-through panel (item 19 — Parth hand-off data)."""
    business_type = str(record.get("business_type") or BusinessType.UNKNOWN.value)
    bq_raw = _float_or_none(record.get("bq_raw")) or 0.0
    base_stored = _float_or_none(record.get("fs_quality_base"))
    base = base_stored if base_stored is not None else 50 + (bq_raw * 2.5)

    pe_pct = _float_or_none(record.get("pe_percentile_20y"))
    if bool(record.get("pe_history_insufficient")):
        pe_pct = None
    oey = _float_or_none(record.get("owner_earnings_yield"))

    components: dict[str, float] = {
        "base": round(base, 2),
        "pe_percentile": _fs_pe_percentile_points(pe_pct),
        "oey": _fs_oey_points(oey, business_type),
    }

    if business_type == BusinessType.BANK.value:
        from .bank_valuation import bank_fs_valuation_slice

        points, ptbv_detail = bank_fs_valuation_slice(record)
        components["ptbv_vs_roe"] = points
        components["_ptbv_detail"] = ptbv_detail  # informational only, not summed by callers using .values() on numerics
    elif business_type == BusinessType.HIGH_MARGIN_HARDWARE.value:
        ev_ebitda = _float_or_none(record.get("ev_fwd_ebitda"))
        components["ev_fwd_ebitda"] = _fs_tiered_points(ev_ebitda, EV_EBITDA_TIERS)
    else:
        ev_rev = _float_or_none(record.get("ev_fwd_rev"))
        tiers = EV_REV_TIERS.get(business_type, EV_REV_TIERS[BusinessType.UNKNOWN.value])
        components["ev_fwd_rev"] = _fs_tiered_points(ev_rev, tiers)

    total = round(clamp(sum(v for k, v in components.items() if isinstance(v, (int, float))), 0, 100), 2)
    return {"components": {k: v for k, v in components.items() if not k.startswith("_")}, "total": total}


def calculate_fs_score(record: dict[str, Any]) -> float:
    """Always derived by summing `fs_score_breakdown()`'s component rows (item 15) —
    never a separately cached number that can drift from them."""
    return fs_score_breakdown(record)["total"]


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


# Markets with no defined yield-trap threshold (item 17) — KR/JP/CN suffixes used to
# silently fall through to the generic 0.06 (US) threshold, meaning e.g. 005930.KS
# could never correctly be evaluated as a yield trap. Per Rohit's explicit guidance
# (matches engine_layers_spec.html's "undefined" rendering for 005930.KS), these now
# return an explicit `None` sentinel instead — `is_yield_trap()` never fires for a
# market with no defined threshold, rather than silently defaulting to the wrong one.
UNDEFINED_YIELD_TRAP_SUFFIXES = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")

BANK_YIELD_TRAP_THRESHOLD_ADDON = 0.02  # +2pp on top of the market threshold, item 3

# The deal-delay valuation tax only applies where there is a growth premium in the price
# to re-rate away (Rohit 1 Sep, C5).
DEAL_DELAY_TAX_EV_REV_FLOOR = 4.0


def market_yield_threshold(ticker: str, business_type: str | None = None) -> float | None:
    symbol = ticker.upper()
    threshold: float | None
    if any(symbol.endswith(suffix) for suffix in UNDEFINED_YIELD_TRAP_SUFFIXES):
        threshold = None
    elif symbol.endswith(".NZ"):
        threshold = 0.12
    elif symbol.endswith(".AX"):
        threshold = 0.10
    elif symbol.endswith(".TO"):
        threshold = 0.07
    elif symbol.endswith(".L"):
        threshold = 0.09
    else:
        threshold = 0.06

    if threshold is not None and str(business_type or "").lower() == BusinessType.BANK.value:
        threshold += BANK_YIELD_TRAP_THRESHOLD_ADDON
    return threshold


def is_yield_trap(record: dict[str, Any], ticker: str) -> bool:
    """Trap when z-score > 1.5 AND yield at or above market threshold; both required.
    Never fires when the market has no defined threshold (item 17)."""
    zscore = _float_or_none(record.get("dividend_yield_zscore"))
    current_yield = _float_or_none(record.get("dividend_yield_current"))
    threshold = market_yield_threshold(ticker, record.get("business_type"))
    record["yield_trap_mkt_threshold"] = threshold
    if zscore is None or current_yield is None or threshold is None:
        return False
    return zscore > 1.5 and current_yield >= threshold


def yield_trap_breakdown(record: dict[str, Any], ticker: str) -> dict[str, Any]:
    """Both conditions' pass/fail + actual numbers, for the Engine Layers "Yield Trap"
    click-through panel and the confirmed-fired vs watching-but-not-fired distinction
    Parth's panel needs (item 19)."""
    zscore = _float_or_none(record.get("dividend_yield_zscore"))
    current_yield = _float_or_none(record.get("dividend_yield_current"))
    threshold = market_yield_threshold(ticker, record.get("business_type"))
    zscore_condition = zscore is not None and zscore > 1.5
    yield_condition = (
        current_yield is not None and threshold is not None and current_yield >= threshold
    )
    # Which dividend the numbers above are built on, plus the trailing-basis answer
    # for comparison. `basis_conflict` True means the trap verdict flips with the
    # basis choice, so the panel should say so instead of showing one silent answer
    # (Rohit 26 Aug, conviction spec gap 4).
    zscore_trailing = _float_or_none(record.get("dividend_yield_zscore_trailing"))
    return {
        "dividend_yield_current": current_yield,
        "dividend_yield_zscore": zscore,
        "dividend_basis": record.get("dividend_yield_basis"),
        "dividend_yield_forward": _float_or_none(record.get("dividend_yield_forward")),
        "dividend_yield_trailing": _float_or_none(record.get("dividend_yield_trailing")),
        "dividend_yield_zscore_trailing": zscore_trailing,
        "basis_conflict": bool(record.get("dividend_basis_conflict")),
        "market_threshold": threshold,
        "market_threshold_defined": threshold is not None,
        "zscore_condition_met": zscore_condition,
        "yield_condition_met": yield_condition,
        "fired": bool(zscore_condition and yield_condition),
        "watching": bool(zscore_condition != yield_condition),
    }


def verdict_for_buy(
    score: float,
    fd_direction: str | None = None,
    yield_trap: bool = False,
    coverage_incomplete: bool = False,
) -> tuple[str, float]:
    # COVERAGE INCOMPLETE (item 5) is a third hard gate, distinct from CANCEL BUY —
    # "we can't score this yet" vs. "we scored it and said no" — same 0% sizing,
    # checked ahead of yield_trap since an uncalibrated business type means the
    # yield-trap threshold itself may not be meaningful either.
    if coverage_incomplete:
        return "COVERAGE INCOMPLETE", 0.0
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


# ── Sell ladder (Rohit 1 Sep, C4) ─────────────────────────────────────────────────
# His complaint was that the label lied about the cause: a conviction of 0 on MCY mapped
# to HARD EXIT, described in the spec as "fundamentals deteriorating or yield trap", when
# MCY had just beaten guidance and cut leverage. The score was low because the PRICE was
# high. So the ladder now reads bq_raw separately from conviction, and every verdict
# carries a reason code saying which of the three cases produced it.
#
#   conviction < +2 and bq_raw < 0        HARD EXIT     retain 0%    QUALITY_COLLAPSE
#   conviction < +2 and bq_raw 0 to +4    FULL EXIT     retain 0%    NORMAL_TECHNICAL
#   conviction < +2 and bq_raw >= +5      PARTIAL EXIT  retain 50%   VALUATION_STRETCH
#   conviction >= +2                      existing v5 table
#
# Hard gates override all of it and force HARD EXIT: yield trap, fs_class weak, or a
# dividend cut with coverage below 1.0x.
SELL_REASON_QUALITY_COLLAPSE = "QUALITY_COLLAPSE"
SELL_REASON_NORMAL_TECHNICAL = "NORMAL_TECHNICAL"
SELL_REASON_VALUATION_STRETCH = "VALUATION_STRETCH"
SELL_REASON_YIELD_TRAP = "YIELD_TRAP"
SELL_REASON_FS_WEAK = "FS_WEAK"
SELL_REASON_DIVIDEND_CUT_UNCOVERED = "DIVIDEND_CUT_UNCOVERED"
SELL_REASON_COVERAGE_INCOMPLETE = "COVERAGE_INCOMPLETE"
SELL_REASON_CONVICTION_INTACT = "CONVICTION_INTACT"

BQ_QUALITY_COLLAPSE_BELOW = 0.0
BQ_VALUATION_STRETCH_AT_OR_ABOVE = 5.0


def verdict_for_sell(
    score: float,
    signal_timeframe: str,
    yield_trap: bool = False,
    coverage_incomplete: bool = False,
    bq_raw: float | None = None,
    fs_class: str | None = None,
    dividend_cut_uncovered: bool = False,
) -> tuple[str, float, str]:
    """Return ``(verdict, retain_pct, sell_reason_code)``.

    ``bq_raw`` is the business-quality score BEFORE the valuation tax, which is the
    whole point: it separates a business whose quality has collapsed from one whose
    price has simply run.
    """
    if coverage_incomplete:
        return "COVERAGE INCOMPLETE", 0.0, SELL_REASON_COVERAGE_INCOMPLETE

    # Hard gates, in his order. Each forces HARD EXIT regardless of bq_raw.
    if yield_trap:
        return "HARD EXIT", 0.0, SELL_REASON_YIELD_TRAP
    if str(fs_class or "").lower() == FsClass.WEAK.value:
        return "HARD EXIT", 0.0, SELL_REASON_FS_WEAK
    if dividend_cut_uncovered:
        return "HARD EXIT", 0.0, SELL_REASON_DIVIDEND_CUT_UNCOVERED

    if score >= 2:
        # Conviction intact — the existing v5 table, unchanged.
        if signal_timeframe == "short":
            if score >= 8:
                return "PAUSE SELL", 0.0, SELL_REASON_CONVICTION_INTACT
            if score >= 5:
                return "PARTIAL EXIT", 0.0, SELL_REASON_CONVICTION_INTACT
            return "FULL EXIT", 0.0, SELL_REASON_CONVICTION_INTACT
        if score >= 8:
            return "PAUSE SELL", 70.0, SELL_REASON_CONVICTION_INTACT
        if score >= 5:
            return "PARTIAL EXIT", 50.0, SELL_REASON_CONVICTION_INTACT
        return "FULL EXIT", 0.0, SELL_REASON_CONVICTION_INTACT

    # Conviction below +2: the cause is decided by business quality, not by the score.
    # A missing bq_raw is treated as the middle case rather than assumed to be collapse.
    bq = bq_raw if bq_raw is not None else 0.0
    if bq < BQ_QUALITY_COLLAPSE_BELOW:
        return "HARD EXIT", 0.0, SELL_REASON_QUALITY_COLLAPSE
    if bq >= BQ_VALUATION_STRETCH_AT_OR_ABOVE:
        # Retain 50%: a quality business that has simply re-rated gets trimmed, not
        # dumped. Retain fractions stay deliberately simple pending Ahil's sizing work.
        return "PARTIAL EXIT", 50.0, SELL_REASON_VALUATION_STRETCH
    return "FULL EXIT", 0.0, SELL_REASON_NORMAL_TECHNICAL
