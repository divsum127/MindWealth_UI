"""Claude web-search agent dimensions for quarterly full recalculation (v6)."""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

_AGENT_SEMAPHORE = threading.Semaphore(4)
_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_score(score: Any, low: int = -1, high: int = 2) -> int:
    try:
        v = int(round(float(score)))
    except (TypeError, ValueError):
        return 0
    return max(low, min(high, v))


def _parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(cleaned)


def _call_claude_web_search(
    *,
    system: str,
    user: str,
    max_tokens: int = 400,
) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=_DEFAULT_MODEL,
        max_tokens=max_tokens,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    result_text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    return _parse_json_text(result_text)


def _apply_confidence_rules(result: dict[str, Any], *, default_score: int = 0) -> dict[str, Any]:
    sources = result.get("sources") or []
    if len(sources) < 2:
        result["confidence"] = min(float(result.get("confidence", 0.3)), 0.35)
    ev_for = str(result.get("evidence_for") or "")
    ev_against = str(result.get("evidence_against") or "")
    if len(ev_against) > len(ev_for) + 30:
        result["confidence"] = min(float(result.get("confidence", 0.5)), 0.55)
    if float(result.get("confidence", 0)) < 0.7:
        result["score"] = default_score
        rationale = str(result.get("rationale") or "")
        if "defaulted" not in rationale.lower():
            result["rationale"] = (rationale + " [defaulted: confidence below threshold]").strip()
    result["score"] = _clamp_score(result.get("score", default_score))
    return result


def compute_macro_tailwind(
    ticker: str,
    company_name: str,
    business_type: str,
    current_year: int | None = None,
) -> dict[str, Any]:
    from datetime import datetime

    year = current_year or datetime.now().year
    system = """You are a fundamental investment analyst. Score conservatively.
Look specifically for THREATS before tailwinds.
Respond ONLY with this exact JSON (no other text, no markdown):
{"score": <-1|0|1|2>,
 "rationale": "<max 120 chars>",
 "key_risk": "<main threat>",
 "evidence_for": "<supporting fact>",
 "evidence_against": "<contradicting fact>",
 "sources": ["<url or source 1>"],
 "confidence": <0.0-1.0>}
If sources list is empty: confidence MUST be below 0.4."""
    user = f"""Search macro environment for {company_name} ({ticker}).
Business type: {business_type}. Year: {year}.
Score NET macro tailwind for THIS company: +2 strong tailwind, +1 mild, 0 neutral, -1 headwind."""

    try:
        with _AGENT_SEMAPHORE:
            result = _call_claude_web_search(system=system, user=user)
        return _apply_confidence_rules(result, default_score=0)
    except Exception as exc:
        logger.warning("[macro_tailwind] %s failed: %s", ticker, exc)
        return {
            "score": 0,
            "rationale": "Agent unavailable — defaulted neutral",
            "key_risk": "",
            "confidence": 0.0,
            "sources": [],
        }


def compute_ceo_quality_agent(ticker: str, company_name: str, current_year: int | None = None) -> dict[str, Any]:
    from datetime import datetime

    year = current_year or datetime.now().year
    system = """Score CEO quality 0-10 for investment quality. Respond ONLY JSON:
{"score_0_10": <0-10>, "rationale": "<max 120 chars>", "sources": [], "confidence": <0-0-1>,
 "evidence_for": "", "evidence_against": ""}"""
    user = f"Search {company_name} ({ticker}) CEO tenure track record domain expertise {year}."

    try:
        with _AGENT_SEMAPHORE:
            raw = _call_claude_web_search(system=system, user=user, max_tokens=350)
        score_10 = _float_or_none(raw.get("score_0_10"))
        if score_10 is None:
            score_10 = _float_or_none(raw.get("score"))
        detail = _apply_confidence_rules(
            {"score": 0, "rationale": raw.get("rationale", ""), "sources": raw.get("sources", []),
             "confidence": raw.get("confidence", 0.5), "evidence_for": raw.get("evidence_for", ""),
             "evidence_against": raw.get("evidence_against", "")},
            default_score=0,
        )
        detail["score_0_10"] = score_10 if score_10 is not None else 5.0
        return detail
    except Exception as exc:
        logger.warning("[ceo_quality] %s failed: %s", ticker, exc)
        return {"score_0_10": 5.0, "rationale": "Agent unavailable", "confidence": 0.0, "sources": []}


def compute_competitive_moat_agent(ticker: str, company_name: str, current_year: int | None = None) -> dict[str, Any]:
    from datetime import datetime

    year = current_year or datetime.now().year
    system = (
        'You are an adversarial investment analyst. First identify the 3 most significant '
        "threats to this company's competitive position, including new entrants, technology "
        "disruption, or margin erosion risks. Only then score overall moat strength. "
        "Apply a conservative bias. Return JSON: "
        '{"score_0_10":<0-10>,"rationale":"<120chars>","threats":["str","str","str"],'
        '"moat_sources":["str"],"evidence_against":"<str>","sources":["str"],"confidence":<float>}'
    )
    user = f"Adversarial moat analysis for {company_name} ({ticker}) in {year}."

    try:
        with _AGENT_SEMAPHORE:
            raw = _call_claude_web_search(system=system, user=user, max_tokens=350)
        score_10 = _float_or_none(raw.get("score_0_10")) or 5.0
        detail = _apply_confidence_rules(
            {
                "score": 0,
                "rationale": raw.get("rationale", ""),
                "sources": raw.get("sources", []),
                "confidence": raw.get("confidence", 0.5),
                "evidence_against": raw.get("evidence_against", ""),
                "threats": raw.get("threats", []),
            },
            default_score=0,
        )
        detail["score_0_10"] = score_10 if float(detail.get("confidence", 0)) >= 0.7 else 5.0
        return detail
    except Exception as exc:
        logger.warning("[competitive_moat] %s failed: %s", ticker, exc)
        return {"score_0_10": 5.0, "rationale": "Agent unavailable", "confidence": 0.0, "sources": []}


def analyst_score_to_bq(score_10: float | None) -> float:
    """0-10 agent score → BQ points."""
    if score_10 is None:
        return 0.0
    if score_10 >= 8:
        return 2.0
    if score_10 >= 5:
        return 1.0
    if score_10 >= 3:
        return 0.0
    return -1.0


def compute_reinvestment_runway_agent(ticker: str, company_name: str, revenue_ttm: float | None = None) -> dict[str, Any]:
    system = """Find official TAM for this company. Priority: Investor Day, earnings calls, Gartner/Grand View.
Return JSON: {"tam_usd": <float|null>, "tam_source": "<source>", "rationale": "<includes TAM value + source>",
"sources": ["url"], "confidence": <0-1>}"""
    user = f"Total addressable market TAM for {company_name} ({ticker}). Revenue TTM USD: {revenue_ttm}"
    try:
        with _AGENT_SEMAPHORE:
            raw = _call_claude_web_search(system=system, user=user, max_tokens=400)
        result = _apply_confidence_rules(raw, default_score=0)
        tam = _float_or_none(raw.get("tam_usd"))
        rev = revenue_ttm
        if tam and rev and rev > 0:
            result["tam_revenue_multiple"] = round(tam / rev, 2)
        return result
    except Exception as exc:
        logger.warning("[reinvestment_runway] %s failed: %s", ticker, exc)
        return {"tam_usd": None, "rationale": "Agent unavailable", "confidence": 0.0, "sources": []}


def run_agent_dimensions(
    ticker: str,
    company_name: str,
    business_type: str,
    *,
    skip_agents: bool = False,
    revenue_ttm: float | None = None,
) -> dict[str, Any]:
    """Run macro / CEO / moat / reinvestment agent calls (sequential with semaphore)."""
    if skip_agents or not os.environ.get("ANTHROPIC_API_KEY"):
        return {}
    return {
        "macro_tailwind_detail": compute_macro_tailwind(ticker, company_name, business_type),
        "ceo_quality_detail": compute_ceo_quality_agent(ticker, company_name),
        "competitive_moat_detail": compute_competitive_moat_agent(ticker, company_name),
        "reinvestment_runway_detail": compute_reinvestment_runway_agent(ticker, company_name, revenue_ttm),
    }
