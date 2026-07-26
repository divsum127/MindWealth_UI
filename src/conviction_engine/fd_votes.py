"""Fundamental Direction — 5-vote majority (v6)."""

from __future__ import annotations

from typing import Any

from .scoring import _float_or_none


def _vote_label(positive: bool, negative: bool) -> str:
    if positive and not negative:
        return "positive"
    if negative and not positive:
        return "negative"
    return "stable"


def compute_fd_votes(fundamentals: dict[str, Any], record: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Five independent votes; majority (>=3) wins. Returns votes dict + fd_direction + fd_sizing_adj.
    """
    record = record or {}
    votes: dict[str, dict[str, Any]] = {}

    # Vote 1 — Revenue acceleration (YoY quarterly sequence improving)
    rev_accel = fundamentals.get("revenue_accelerating")
    if rev_accel is True:
        votes["revenue"] = {"vote": "positive", "rationale": "revenue_accelerating=True"}
    else:
        votes["revenue"] = {"vote": "stable", "rationale": "revenue not accelerating or unknown"}

    # Vote 2 — Margins YoY (gross margin trend as proxy)
    margin_trend = _float_or_none(fundamentals.get("gross_margin_trend"))
    if margin_trend is not None:
        if margin_trend >= 0.01:
            votes["margins"] = {"vote": "positive", "rationale": f"gross_margin_trend {margin_trend:.2%} >= 100bp"}
        elif margin_trend <= -0.01:
            votes["margins"] = {"vote": "negative", "rationale": f"gross_margin_trend {margin_trend:.2%} <= -100bp"}
        else:
            votes["margins"] = {"vote": "stable", "rationale": "margins within ±100bp"}
    else:
        votes["margins"] = {"vote": "stable", "rationale": "gross_margin_trend missing"}

    # Vote 3 — FCF YoY + margin expanding
    fcf_ttm = _float_or_none(fundamentals.get("fcf_ttm") or record.get("fcf_ttm"))
    fcf_prior = _float_or_none(fundamentals.get("fcf_prior_year"))
    fcf_margin = _float_or_none(fundamentals.get("fcf_margin"))
    fcf_margin_prior = _float_or_none(fundamentals.get("fcf_margin_prior"))
    margin_exp = (
        fcf_margin is not None
        and fcf_margin_prior is not None
        and fcf_margin > fcf_margin_prior
    )
    if fcf_ttm is not None and fcf_prior is not None:
        if fcf_ttm > fcf_prior and (margin_exp or fcf_margin is None):
            votes["fcf"] = {"vote": "positive", "rationale": "FCF growing YoY"}
        elif fcf_ttm < fcf_prior * 0.95:
            votes["fcf"] = {"vote": "negative", "rationale": "FCF down >5% YoY"}
        else:
            votes["fcf"] = {"vote": "stable", "rationale": "FCF flat YoY"}
    else:
        fcf_growth = _float_or_none(fundamentals.get("fcf_growth_yoy"))
        if fcf_growth is not None and fcf_growth > 0 and (margin_exp or fcf_margin is None):
            votes["fcf"] = {"vote": "positive", "rationale": "FCF growing YoY"}
        elif fcf_growth is not None and fcf_growth < -0.05:
            votes["fcf"] = {"vote": "negative", "rationale": "FCF declining YoY"}
        else:
            votes["fcf"] = {"vote": "stable", "rationale": "FCF flat or unknown"}

    # Vote 4 — EPS revisions vs stored prior
    eps_est = _float_or_none(fundamentals.get("eps_estimate_current") or record.get("eps_estimate_current"))
    eps_prior = _float_or_none(fundamentals.get("eps_estimate_prior") or record.get("eps_estimate_prior"))
    if eps_est is not None and eps_prior is not None and eps_prior > 0:
        change = (eps_est - eps_prior) / abs(eps_prior)
        if change >= 0.03:
            votes["eps_revisions"] = {"vote": "positive", "rationale": f"EPS estimate +{change:.1%}"}
        elif change <= -0.03:
            votes["eps_revisions"] = {"vote": "negative", "rationale": f"EPS estimate {change:.1%}"}
        else:
            votes["eps_revisions"] = {"vote": "stable", "rationale": "EPS estimate within ±3%"}
    else:
        votes["eps_revisions"] = {"vote": "stable", "rationale": "EPS revision data missing"}

    # Vote 5 — Buybacks (shares outstanding change TTM)
    shares_change = _float_or_none(fundamentals.get("shares_outstanding_change_pct"))
    if shares_change is not None:
        if shares_change <= -0.01:
            votes["buybacks"] = {"vote": "positive", "rationale": f"shares down {shares_change:.1%} TTM"}
        elif shares_change >= 0.01:
            votes["buybacks"] = {"vote": "negative", "rationale": f"shares up {shares_change:.1%} TTM"}
        else:
            votes["buybacks"] = {"vote": "stable", "rationale": "share count flat"}
    else:
        votes["buybacks"] = {"vote": "stable", "rationale": "shares history missing"}

    pos = sum(1 for v in votes.values() if v["vote"] == "positive")
    neg = sum(1 for v in votes.values() if v["vote"] == "negative")

    if pos >= 3:
        direction = "positive"
        sizing_adj = 0.10
    elif neg >= 3:
        direction = "negative"
        sizing_adj = -0.15
    else:
        direction = "stable"
        sizing_adj = 0.0

    return {
        "votes": votes,
        "fd_direction": direction,
        "fd_sizing_adj": sizing_adj,
        "positive_count": pos,
        "negative_count": neg,
    }
