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
    system = """Score CEO quality 0-10 for investment quality. Search first, then fetch the
specific URL search returns — do not attempt a direct domain fetch. Good source hints:
Harvard Business Review's "Best-Performing CEOs" rankings (tenure-based financial + ESG
performance — cite even if the ranking edition is a few years old, note it as dated
directional evidence), LinkedIn (employee/analyst commentary), Comparably (employee-rated
CEO scores). Respond ONLY JSON:
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


def compute_competitive_moat_agent(
    ticker: str,
    company_name: str,
    current_year: int | None = None,
    is_hardware_sector: bool = False,
) -> dict[str, Any]:
    from datetime import datetime

    year = current_year or datetime.now().year
    system = (
        'You are an adversarial investment analyst. First identify the 3 most significant '
        "threats to this company's competitive position, including new entrants, technology "
        "disruption, or margin erosion risks. Only then score overall moat strength. "
        "Apply a conservative bias. "
    )
    if is_hardware_sector:
        # Item 6 (Q3 answer): G2 measures software UX satisfaction, not chip/hardware
        # competitive position — keyed off raw sector/industry tokens so it applies to
        # every semiconductor/hardware name, not just the ones that clear the 40%
        # high_margin_hardware margin test.
        system += (
            "This is a semiconductor/hardware company: do NOT use G2 as a source, it "
            "measures software UX satisfaction and is not relevant here. Prefer Gartner, "
            "patent-database filings, and industry-analyst reports instead. "
        )
    system += (
        "Search first, then fetch the specific URL returned by search — do not attempt a "
        "direct domain fetch. Return JSON: "
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


def compute_deal_delay_agent(ticker: str, company_name: str, current_year: int | None = None) -> dict[str, Any]:
    """Dim 13 (deal-delay / decel risk) — the 4th fully-agentic BQ dimension, previously
    override-only (``deal_delay_risk``/``deal_delay_flag`` in `fundamentals_enriched.py`).

    Per item 9 (Q8 answer / Section 9 of the 28 July note), a transcript scan can surface
    two mutually-exclusive, opposite-implication signals — this agent asks for both in one
    pass so a supply-constrained name (e.g. GOOGL's Q2 2026 backlog commentary) never gets
    silently forced into the deal-delay bucket for lack of a distinct flag:
    - ``deal_delay``: timing-slippage language (deals pushed out, elongated sales cycles,
      customs/regulatory holds) — negative demand signal, BQ -1/-2.
    - ``supply_constraint``: capacity-rationing / backlog-growth language — demand
      *exceeds* supply, opposite direction — informational only (item 9), never negative.
    """
    from datetime import datetime

    year = current_year or datetime.now().year
    system = """You are a fundamental analyst scanning the most recent earnings call
transcript for exactly two distinct, mutually-exclusive signals — decide which one (if
any) actually applies, do not force a result:
1. deal_delay: deals/orders pushed out, elongated sales cycles, customs/regulatory
   shipment holds, customer budget freezes — a NEGATIVE demand signal.
2. supply_constraint: capacity being rationed, backlog growing faster than it can be
   fulfilled, demand outstripping supply — the OPPOSITE signal (often a positive demand
   proxy paired with a margin/capex risk, not a negative one).
If transcript language does not clearly support either, use "none".
Respond ONLY with this exact JSON (no other text, no markdown):
{"signal": "<deal_delay|supply_constraint|none>",
 "score": <-2|-1|0>,
 "rationale": "<max 120 chars>",
 "supply_constraint_detail": "<backlog $ / capacity detail if signal=supply_constraint, else empty>",
 "evidence_for": "<supporting quote/fact>",
 "evidence_against": "<contradicting fact>",
 "sources": ["<url>"],
 "confidence": <0.0-1.0>}
score MUST be 0 unless signal is "deal_delay" (then -1 mild / -2 severe timing slippage).
If sources list is empty: confidence MUST be below 0.4."""
    user = f"Search the most recent earnings call transcript for {company_name} ({ticker}), {year}, for deal-delay or supply-constraint language."

    try:
        with _AGENT_SEMAPHORE:
            result = _call_claude_web_search(system=system, user=user, max_tokens=350)
        detail = _apply_confidence_rules(result, default_score=0)
        if detail.get("signal") != "deal_delay":
            detail["score"] = 0
        return detail
    except Exception as exc:
        logger.warning("[deal_delay] %s failed: %s", ticker, exc)
        return {
            "signal": "none",
            "score": 0,
            "rationale": "Agent unavailable — defaulted neutral",
            "supply_constraint_detail": "",
            "confidence": 0.0,
            "sources": [],
        }


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


def compute_reinvestment_runway_agent(
    ticker: str,
    company_name: str,
    revenue_ttm: float | None = None,
    backlog_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dim 15 (TAM / reinvestment runway) — Tiers 2+3 of the three-tier sourcing split
    (item 20 / Section 12.1): company-stated TAM (transcript text extraction) plus an
    independent third-party market-size estimate (search-then-fetch of a public
    press-release headline number), asked for together so the agent can cross-check one
    against the other rather than reporting a single unverified figure.

    Tier 1 (mechanical SEC XBRL revenue-backlog fact, ``tam_sourcing.py``) is fetched by
    the caller and passed in as ``backlog_detail`` — for companies that don't publish a
    TAM number at all (e.g. GOOGL per the note's own worked example), the backlog is the
    best structured demand proxy and is threaded into the prompt as context rather than
    forcing the agent to guess or leave the whole dimension blank.
    """
    backlog_note = ""
    if backlog_detail and backlog_detail.get("backlog_usd"):
        backlog_note = (
            f" Company's SEC-filed remaining performance obligation (backlog) as of "
            f"{backlog_detail.get('as_of')}: ${backlog_detail['backlog_usd']:,.0f} — use this as a "
            f"structured demand proxy if no company-stated TAM figure exists, and note it in the rationale."
        )
    system = """Find TWO things for this company, not one:
1. Company-stated TAM: management's own spoken figure from an earnings call, investor
   day, or keynote (e.g. "$3-4T AI infrastructure spend by 2030") — search transcripts
   (Motley Fool / Seeking Alpha / company IR all work), this is spoken commentary, not a
   filed number.
2. Independent third-party market-size estimate: a named research firm's headline number
   (IDC, Gartner, Synergy Research, SIA-Deloitte, Persistence Market Research, Grand View
   Research, etc.) as a cross-check against #1 — search first, then fetch the specific
   URL search returns (these firms publish headline numbers on free press-release pages
   specifically to be cited; do not attempt a direct domain fetch).
If the company doesn't publish a TAM figure, say so explicitly and rely on #2 plus any
backlog/demand-proxy context provided.
Return JSON: {"tam_usd": <float|null, company-stated>, "tam_source": "<source>",
"independent_tam_usd": <float|null>, "independent_tam_source": "<research firm + report>",
"rationale": "<includes both figures + sources, and a note if they diverge meaningfully>",
"sources": ["url"], "confidence": <0-1>}"""
    user = (
        f"Total addressable market TAM for {company_name} ({ticker}). Revenue TTM USD: {revenue_ttm}."
        + backlog_note
    )
    try:
        with _AGENT_SEMAPHORE:
            raw = _call_claude_web_search(system=system, user=user, max_tokens=450)
        result = _apply_confidence_rules(raw, default_score=0)
        if backlog_detail:
            result["revenue_backlog_detail"] = backlog_detail
        tam = _float_or_none(raw.get("tam_usd"))
        independent_tam = _float_or_none(raw.get("independent_tam_usd"))
        result["independent_tam_usd"] = independent_tam
        result["independent_tam_source"] = raw.get("independent_tam_source")
        rev = revenue_ttm
        # Prefer the company-stated figure for the sizing ratio when available (matches
        # the original spec's TAM-vs-revenue runway framing); fall back to the
        # independent estimate when the company doesn't publish its own number.
        multiple_basis = tam if tam is not None else independent_tam
        if multiple_basis and rev and rev > 0:
            result["tam_revenue_multiple"] = round(multiple_basis / rev, 2)
        return result
    except Exception as exc:
        logger.warning("[reinvestment_runway] %s failed: %s", ticker, exc)
        return {
            "tam_usd": None,
            "independent_tam_usd": None,
            "revenue_backlog_detail": backlog_detail,
            "rationale": "Agent unavailable",
            "confidence": 0.0,
            "sources": [],
        }


def run_agent_dimensions(
    ticker: str,
    company_name: str,
    business_type: str,
    *,
    skip_agents: bool = False,
    revenue_ttm: float | None = None,
    is_hardware_sector: bool = False,
) -> dict[str, Any]:
    """Run macro / CEO / moat / deal-delay / reinvestment agent calls (sequential with
    semaphore). Deal-delay (item 20) is the 4th fully-agentic BQ dimension, previously
    override-only. Reinvestment-runway's Tier-1 revenue-backlog fact (item 20 /
    Section 12.1) is fetched mechanically here — zero agentic cost — before the Tier-2/3
    agent call, so it's available as demand-proxy context for names with no TAM figure.
    """
    if skip_agents or not os.environ.get("ANTHROPIC_API_KEY"):
        return {}
    from .tam_sourcing import fetch_revenue_backlog_xbrl

    try:
        backlog_detail = fetch_revenue_backlog_xbrl(ticker)
    except Exception as exc:
        logger.warning("[revenue_backlog] %s failed: %s", ticker, exc)
        backlog_detail = None

    return {
        "macro_tailwind_detail": compute_macro_tailwind(ticker, company_name, business_type),
        "ceo_quality_detail": compute_ceo_quality_agent(ticker, company_name),
        "competitive_moat_detail": compute_competitive_moat_agent(ticker, company_name, is_hardware_sector=is_hardware_sector),
        "deal_delay_detail": compute_deal_delay_agent(ticker, company_name),
        "reinvestment_runway_detail": compute_reinvestment_runway_agent(ticker, company_name, revenue_ttm, backlog_detail),
    }
