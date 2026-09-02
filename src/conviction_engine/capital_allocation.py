"""Capital allocation dimension — float reduction / buyback scoring."""

from __future__ import annotations

from typing import Any

from .scoring import _float_or_none


def buyback_score_0_10(buyback_pct: float) -> int:
    """buyback_pct = (shares_12m_ago - shares_now) / shares_12m_ago"""
    if buyback_pct >= 0.07:
        return 9
    if buyback_pct >= 0.01:
        return 8
    if buyback_pct >= 0.005:
        return 6
    if buyback_pct >= 0.0:
        return 4
    if buyback_pct >= -0.02:
        return 2
    return 0


def score_0_10_to_bq(score_10: float) -> float:
    if score_10 >= 8:
        return 2.0
    if score_10 >= 6:
        return 1.0
    if score_10 >= 3:
        return 0.0
    return -1.0


def compute_buyback_pct(fundamentals: dict[str, Any], info: dict[str, Any] | None = None) -> float | None:
    """Shares retired over trailing 12 months."""
    info = info or {}
    change = _float_or_none(fundamentals.get("shares_outstanding_change_pct"))
    if change is not None:
        return -change  # negative change_pct means shares down → positive buyback

    shares_now = _float_or_none(fundamentals.get("shares_outstanding_now") or info.get("sharesOutstanding"))
    shares_12m = _float_or_none(fundamentals.get("shares_outstanding_12m_ago"))
    if shares_now and shares_12m and shares_12m > 0:
        return (shares_12m - shares_now) / shares_12m
    return None


def score_capital_allocation(
    fundamentals: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    info: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    overrides = overrides or {}
    if overrides.get("mgmt_alloc_score") is not None:
        from .scoring import score_manual

        return score_manual("mgmt_alloc_score", overrides), {}

    buyback_pct = compute_buyback_pct(fundamentals, info)
    if buyback_pct is None:
        return 0.0, {}
    score_10 = buyback_score_0_10(buyback_pct)
    return score_0_10_to_bq(float(score_10)), {
        "buyback_pct": round(buyback_pct, 4),
        "score_0_10": score_10,
    }


# --- Item 7: standalone buyback-suspension / dividend-cut penalty flags ---------
#
# Structurally separate from `mgmt_capital_allocation` (the share-count-based buyback
# vote above, which keeps running unchanged) and from `balance_sheet` — own dict
# entries, folded into bq_components as their own "capital_return_flags" key, to
# avoid double-counting a single capital-return deterioration against two dimensions.

BUYBACK_SUSPENSION_MIN_PRIOR_SPEND = 100_000_000.0  # trigger only fires above this prior-period spend
CAPITAL_RETURN_COMBINED_FLOOR = -4.0  # both flags firing together caps at -4, not -6


def _decline_pct(current: float | None, prior: float | None) -> float | None:
    if prior is None or prior <= 0:
        return None
    return (prior - (current or 0.0)) / prior


def _tiered_decline_penalty(decline_pct: float | None) -> float:
    """0-25% decline -> no trigger; 25-50% -> -1; 50-75% -> -2; 75-100%+ -> -3."""
    if decline_pct is None:
        return 0.0
    if decline_pct <= 0.25:
        return 0.0
    if decline_pct <= 0.50:
        return -1.0
    if decline_pct <= 0.75:
        return -2.0
    return -3.0


def detect_buyback_suspension(fundamentals: dict[str, Any]) -> dict[str, Any]:
    """Spend-based buyback-suspension flag: requires prior-period buyback spend
    > $100M before the tiered period-over-period decline penalty can fire."""
    current = _float_or_none(fundamentals.get("buyback_spend_ttm"))
    prior = _float_or_none(fundamentals.get("buyback_spend_prior_year"))
    result: dict[str, Any] = {
        "triggered": False,
        "penalty": 0.0,
        "decline_pct": None,
        "current_spend": current,
        "prior_spend": prior,
    }
    if prior is None or prior < BUYBACK_SUSPENSION_MIN_PRIOR_SPEND:
        return result
    decline = _decline_pct(current, prior)
    penalty = _tiered_decline_penalty(decline)
    result["decline_pct"] = round(decline, 4) if decline is not None else None
    result["penalty"] = penalty
    result["triggered"] = penalty < 0.0
    return result


def detect_dividend_cut(fundamentals: dict[str, Any]) -> dict[str, Any]:
    """Declared-annual-dividend-per-share tiered decline flag (same tier structure
    as buyback suspension, no minimum-size gate — any declared dividend cut counts).

    Rohit 1 Sep, C3: "A cut that's a deliberate reset to an FCF-linked payout with
    leverage falling is good capital allocation, not distress. Spark is exactly that —
    net debt down 35%, payout now 90-100% of FCF. Rule: full penalty only where coverage
    deteriorates or leverage rises alongside the cut. Otherwise half penalty, flagged
    policy_reset."

    The three comparisons are against the prior stored record and both inputs are
    already carried: distribution coverage and net-debt-to-EBITDA.
    """
    current = _float_or_none(fundamentals.get("annual_div_declared_current"))
    prior = _float_or_none(fundamentals.get("annual_div_declared_prior"))
    result: dict[str, Any] = {
        "triggered": False,
        "penalty": 0.0,
        "decline_pct": None,
        "current_rate": current,
        "prior_rate": prior,
        "policy_reset": False,
        "distress_signals": [],
    }
    if prior is None or prior <= 0:
        return result
    decline = _decline_pct(current, prior)
    penalty = _tiered_decline_penalty(decline)
    result["decline_pct"] = round(decline, 4) if decline is not None else None

    if penalty < 0.0:
        # Does the cut come with deteriorating coverage or rising leverage?
        distress: list[str] = []
        coverage_now = _float_or_none(fundamentals.get("distribution_coverage_ratio"))
        coverage_prior = _float_or_none(fundamentals.get("distribution_coverage_ratio_prior"))
        if coverage_now is not None and coverage_prior is not None and coverage_now < coverage_prior:
            distress.append("coverage_deteriorated")
        if coverage_now is not None and coverage_now < 1.0:
            distress.append("coverage_below_1x")
        leverage_now = _float_or_none(fundamentals.get("net_debt_ebitda"))
        leverage_prior = _float_or_none(fundamentals.get("net_debt_ebitda_prior"))
        if leverage_now is not None and leverage_prior is not None and leverage_now > leverage_prior:
            distress.append("leverage_rose")

        # A reset has to be evidenced, not merely un-contradicted. Requiring positive
        # improvement — coverage up or leverage down — rather than accepting the absence
        # of distress means a cut to zero on a name we hold no coverage data for takes
        # the full penalty instead of a discount it has not earned. Spark still gets the
        # half penalty because both of its comparisons genuinely improved.
        improvement: list[str] = []
        if coverage_now is not None and coverage_prior is not None and coverage_now > coverage_prior:
            improvement.append("coverage_improved")
        if leverage_now is not None and leverage_prior is not None and leverage_now < leverage_prior:
            improvement.append("leverage_fell")

        result["distress_signals"] = distress
        result["improvement_signals"] = improvement
        if distress or not improvement:
            result["penalty"] = penalty
        else:
            # Deliberate reset to a sustainable payout: half penalty, flagged.
            result["penalty"] = penalty / 2.0
            result["policy_reset"] = True
    result["triggered"] = result["penalty"] < 0.0
    return result


def combined_capital_return_penalty(buyback_flag: dict[str, Any], dividend_flag: dict[str, Any]) -> float:
    """Cap the combined buyback-suspension + dividend-cut penalty at -4 total,
    not letting them stack to -6 when both fire in the same quarter."""
    total = float(buyback_flag.get("penalty") or 0.0) + float(dividend_flag.get("penalty") or 0.0)
    return max(CAPITAL_RETURN_COMBINED_FLOOR, total)
