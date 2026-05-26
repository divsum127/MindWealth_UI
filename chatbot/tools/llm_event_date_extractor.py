"""
LLM-based extraction of block-sale event dates and parties from web evidence.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from chatbot.config import DEEP_RESEARCH_PLANNER_MODEL, OPENAI_API_KEY
from chatbot.tools.event_date_extractor import known_fallback_date

logger = logging.getLogger(__name__)

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_PRECEDENT_HINTS: Dict[str, str] = {
    "z energy": (
        "Infratil sold 20% of Z Energy via block trade/book build "
        "29–30 September 2015; announcement 1 October 2015; settlement ~6 October 2015. "
        "Seller: Infratil (IFT.NZ). Sold: Z Energy (ZEL.NZ). "
        "IGNORE: June 2015 Chevron acquisition, FY 31 March dividend dates, Contact 2026 noise."
    ),
    "origin": (
        "Origin Energy sold Contact Energy stake announced 4 August 2015, "
        "settlement ~10 August 2015. Seller: Origin (ORG.AX). Sold: Contact (CEN.NZ)."
    ),
    "contact 2015": (
        "Same as Origin / Contact August 2015 block sale."
    ),
    "air new zealand": (
        "NZ Government (Crown) sold down AIR.NZ stake announced 17 November 2013; "
        "seller is NOT Air New Zealand — Crown has no listed ticker. "
        "Sold stock: AIR.NZ. IGNORE: June 2013 livery, unrelated block-trade tables (Trade Me 2012)."
    ),
    "air nz": (
        "Government Crown sell-down November 2013; sold AIR.NZ only."
    ),
}

EVENT_DATE_LLM_SYSTEM = """You extract the primary EVENT DATE for a historical NZ block sale / divestment from web search snippets.

Return ONLY valid JSON:
{
  "event_date": "YYYY-MM-DD",
  "announcement_date": "YYYY-MM-DD or null",
  "settlement_date": "YYYY-MM-DD or null",
  "seller_name": "string",
  "seller_ticker": "TICKER.NZ/.AX or null if unlisted (e.g. Crown/Government)",
  "sold_name": "string",
  "sold_ticker": "TICKER.NZ or null",
  "seller_is_listed": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "one sentence citing which source phrase you used"
}

Rules:
- event_date = best date for measuring post-sale share prices (usually announcement or book-build close, not FY year-end or dividend dates).
- For government sell-downs, seller_is_listed=false and seller_ticker=null; still set sold_ticker.
- Reject dates from unrelated events (bond offers, livery launches, other companies' block trades in a table).
- If snippets clearly describe the precedent, confidence >= 0.7.
- If ambiguous, use null event_date and confidence < 0.5."""


@dataclass
class EventDateExtractionResult:
    event_date: Optional[str] = None
    announcement_date: Optional[str] = None
    settlement_date: Optional[str] = None
    seller_name: Optional[str] = None
    seller_ticker: Optional[str] = None
    sold_name: Optional[str] = None
    sold_ticker: Optional[str] = None
    seller_is_listed: bool = True
    confidence: float = 0.0
    reasoning: str = ""
    source: str = "none"  # llm | heuristic | fallback

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _precedent_hint(precedent_name: Optional[str]) -> str:
    pn = (precedent_name or "").lower()
    parts = []
    for key, hint in _PRECEDENT_HINTS.items():
        if key in pn:
            parts.append(hint)
    return "\n".join(parts) if parts else "(no catalog hint)"


def _format_sources(sources: List[Dict[str, Any]], max_chars: int = 14000) -> str:
    blocks: List[str] = []
    total = 0
    for i, src in enumerate(sources[:12], 1):
        title = (src.get("title") or "").strip()
        url = (src.get("url") or "").strip()
        content = (src.get("content") or "").strip()[:2500]
        block = f"--- Source {i} ---\nTitle: {title}\nURL: {url}\n{content}\n"
        if total + len(block) > max_chars:
            block = block[: max_chars - total]
            blocks.append(block)
            break
        blocks.append(block)
        total += len(block)
    return "\n".join(blocks)


def _normalize_iso(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("null", "none"):
        return None
    if _ISO_RE.match(s):
        return s
    return None


def _normalize_ticker(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().upper()
    if not s or s in ("NULL", "NONE", "N/A"):
        return None
    return s


def _parse_llm_json(data: dict) -> EventDateExtractionResult:
    seller_ticker = _normalize_ticker(data.get("seller_ticker"))
    sold_ticker = _normalize_ticker(data.get("sold_ticker"))

    return EventDateExtractionResult(
        event_date=_normalize_iso(data.get("event_date")),
        announcement_date=_normalize_iso(data.get("announcement_date")),
        settlement_date=_normalize_iso(data.get("settlement_date")),
        seller_name=(str(data["seller_name"]).strip() if data.get("seller_name") else None),
        seller_ticker=seller_ticker,
        sold_ticker=sold_ticker,
        seller_is_listed=bool(data.get("seller_is_listed", seller_ticker is not None)),
        confidence=float(data.get("confidence") or 0),
        reasoning=str(data.get("reasoning") or "").strip(),
        source="llm",
    )


class LlmEventDateExtractor:
    """OpenAI tool to extract block-sale dates from web search evidence."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._api_key = api_key if api_key is not None else OPENAI_API_KEY
        self._model = model or DEEP_RESEARCH_PLANNER_MODEL
        self._client = None
        if self._api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self._api_key)
            except Exception as exc:
                logger.error("LlmEventDateExtractor init failed: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def extract(
        self,
        *,
        question: str,
        sources: List[Dict[str, Any]],
        precedent_name: Optional[str] = None,
        seller_ticker: Optional[str] = None,
        sold_ticker: Optional[str] = None,
        text_blob: Optional[str] = None,
    ) -> EventDateExtractionResult:
        if not self._client:
            return EventDateExtractionResult(
                reasoning="LLM unavailable",
                source="none",
            )

        evidence = _format_sources(sources)
        if text_blob:
            evidence = evidence + "\n\n--- Additional context ---\n" + text_blob[:4000]

        user = (
            f"Research question: {question}\n\n"
            f"Precedent: {precedent_name or 'unknown'}\n"
            f"Expected seller ticker (hint): {seller_ticker or 'unknown'}\n"
            f"Expected sold ticker (hint): {sold_ticker or 'unknown'}\n\n"
            f"Catalog hints:\n{_precedent_hint(precedent_name)}\n\n"
            f"WEB EVIDENCE:\n{evidence}"
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": EVENT_DATE_LLM_SYSTEM},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=400,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
            result = _parse_llm_json(data)
            if result.event_date:
                logger.info(
                    "[DEEP_RESEARCH] LLM event date %s for %s (conf=%.2f)",
                    result.event_date,
                    precedent_name,
                    result.confidence,
                )
            return result
        except Exception as exc:
            logger.error("LlmEventDateExtractor failed: %s", exc)
            return EventDateExtractionResult(
                reasoning=f"LLM error: {exc}",
                source="none",
            )


_default_extractor: Optional[LlmEventDateExtractor] = None


def get_llm_event_date_extractor() -> LlmEventDateExtractor:
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = LlmEventDateExtractor()
    return _default_extractor


def extract_event_date_from_web(
    *,
    question: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    text_blob: str = "",
    precedent_name: Optional[str] = None,
    seller_ticker: Optional[str] = None,
    sold_ticker: Optional[str] = None,
    use_llm: bool = True,
    min_llm_confidence: float = 0.55,
) -> EventDateExtractionResult:
    """
    Resolve event date: LLM on structured sources, then heuristic, then catalog fallback.
    """
    from chatbot.tools.event_date_extractor import best_event_date

    src_list = sources or []
    llm_result: Optional[EventDateExtractionResult] = None

    if use_llm and src_list:
        llm_result = get_llm_event_date_extractor().extract(
            question=question,
            sources=src_list,
            precedent_name=precedent_name,
            seller_ticker=seller_ticker,
            sold_ticker=sold_ticker,
            text_blob=text_blob,
        )
        if (
            llm_result.event_date
            and llm_result.confidence >= min_llm_confidence
        ):
            return llm_result

    blob = text_blob or _format_sources(src_list)
    heuristic_date = best_event_date(
        blob,
        precedent_name=precedent_name,
        sold_ticker=sold_ticker,
        seller_ticker=seller_ticker,
    )
    if heuristic_date:
        out = EventDateExtractionResult(
            event_date=heuristic_date,
            seller_ticker=seller_ticker,
            sold_ticker=sold_ticker,
            confidence=0.45,
            reasoning="Regex/heuristic date scoring on web blob",
            source="heuristic",
        )
        if llm_result and llm_result.sold_ticker:
            out.sold_ticker = llm_result.sold_ticker
        if llm_result and llm_result.seller_ticker:
            out.seller_ticker = llm_result.seller_ticker
        if llm_result and not llm_result.seller_is_listed:
            out.seller_is_listed = False
            out.seller_ticker = None
        return out

    fb = known_fallback_date(precedent_name, sold_ticker)
    if fb:
        return EventDateExtractionResult(
            event_date=fb,
            seller_ticker=seller_ticker,
            sold_ticker=sold_ticker,
            confidence=0.35,
            reasoning="Known precedent catalog fallback",
            source="fallback",
        )

    if llm_result and llm_result.event_date:
        return llm_result

    return EventDateExtractionResult(
        reasoning=llm_result.reasoning if llm_result else "No date extracted",
        source="none",
    )
