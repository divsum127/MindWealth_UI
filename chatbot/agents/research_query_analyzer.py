"""
ResearchQueryAnalyzer — structured intent before subtask planning.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

RESEARCH_QUERY_ANALYSIS_SYSTEM = """You analyze a user question for Deep Research planning.

Return JSON describing:
- comparison_type: "historical_precedents" | "current_event_only" | "mixed" | "general"
- reference_event: optional current deal mentioned (seller_ticker, sold_ticker, status, note) — CONTEXT ONLY unless user asks to track THIS deal forward
- measure_forward_returns_for_reference: false when user asks about PAST similar situations while mentioning a current in-progress sale
- required_outputs: list like seller_T+1m, sold_T+3m, etc.
- suggested_precedents: company names for NZ historical block sales (Z Energy, Trustpower, Genesis, Meridian, Mercury, Air NZ, etc.)

Rules:
- "similar situations in years gone by" / "precedents" → historical_precedents, measure_forward_returns_for_reference=false
- Current block sale tickers are context, NOT the primary measurement target unless user explicitly wants forward returns on THAT sale
- For CEN/Contact + block sale + historical: suggested_precedents should start with Origin Energy / Contact 2015, then Z Energy / Infratil 2015, Air New Zealand 2013, Auckland Airport 2024
- Respond with ONLY valid JSON."""

RESEARCH_QUERY_ANALYSIS_USER = """User question:
{query}

Recent conversation (trimmed):
{history}

JSON schema:
{{
  "comparison_type": "historical_precedents",
  "reference_event": {{
    "seller_ticker": "IFT.NZ",
    "sold_ticker": "CEN.NZ",
    "status": "in_progress",
    "note": "optional"
  }} or null,
  "measure_forward_returns_for_reference": false,
  "required_outputs": ["seller_T+1m", "seller_T+3m", "seller_T+6m", "sold_T+1m", "sold_T+3m", "sold_T+6m"],
  "suggested_precedents": ["Z Energy", "Trustpower", "Genesis Energy"]
}}"""


@dataclass
class ResearchQueryAnalysis:
    comparison_type: str = "general"
    reference_event: Optional[Dict[str, Any]] = None
    measure_forward_returns_for_reference: bool = False
    required_outputs: List[str] = field(default_factory=list)
    suggested_precedents: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comparison_type": self.comparison_type,
            "reference_event": self.reference_event,
            "measure_forward_returns_for_reference": self.measure_forward_returns_for_reference,
            "required_outputs": self.required_outputs,
            "suggested_precedents": self.suggested_precedents,
            "raw": self.raw,
        }

    def format_for_planner(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class ResearchQueryAnalyzer:
    def __init__(self, api_key: Optional[str], model: str = "gpt-4o-mini"):
        self._model = model
        self._client = None
        if api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
            except Exception as exc:
                logger.error(f"ResearchQueryAnalyzer: OpenAI init failed: {exc}")

    def analyze(
        self,
        user_message: str,
        history_messages: Optional[List[Dict]] = None,
    ) -> ResearchQueryAnalysis:
        if self._client:
            try:
                history = self._format_history(history_messages or [])
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": RESEARCH_QUERY_ANALYSIS_SYSTEM},
                        {
                            "role": "user",
                            "content": RESEARCH_QUERY_ANALYSIS_USER.format(
                                query=user_message.strip(),
                                history=history or "(none)",
                            ),
                        },
                    ],
                    response_format={"type": "json_object"},
                    max_completion_tokens=500,
                    temperature=0,
                )
                data = json.loads(response.choices[0].message.content.strip())
                return self._from_dict(data)
            except Exception as exc:
                logger.error(f"ResearchQueryAnalyzer LLM failed: {exc}")
        return self._rule_based(user_message)

    def _from_dict(self, data: dict) -> ResearchQueryAnalysis:
        ref = data.get("reference_event")
        if ref is not None and not isinstance(ref, dict):
            ref = None
        precedents = data.get("suggested_precedents") or []
        if not isinstance(precedents, list):
            precedents = []
        outputs = data.get("required_outputs") or []
        if not isinstance(outputs, list):
            outputs = []
        return ResearchQueryAnalysis(
            comparison_type=str(data.get("comparison_type", "general")),
            reference_event=ref,
            measure_forward_returns_for_reference=bool(
                data.get("measure_forward_returns_for_reference", False)
            ),
            required_outputs=[str(x) for x in outputs],
            suggested_precedents=[str(x) for x in precedents],
            raw=data,
        )

    @staticmethod
    def _rule_based(user_message: str) -> ResearchQueryAnalysis:
        text = (user_message or "").lower()
        historical = bool(
            re.search(
                r"\b(similar|years gone by|precedent|historical|in the past|what happened after)\b",
                text,
                re.I,
            )
        )
        block_sale = bool(re.search(r"\b(block sale|block trade|divestment|selldown)\b", text, re.I))

        seller = None
        sold = None
        if re.search(r"\b(infratil|ift)\b", text, re.I):
            seller = "IFT.NZ"
        if re.search(r"\b(contact|cen\.nz|cen)\b", text, re.I):
            sold = "CEN.NZ"

        ref = None
        if seller or sold:
            ref = {
                "seller_ticker": seller,
                "sold_ticker": sold,
                "status": "in_progress" if re.search(r"\bbeing sold|block sale\b", text, re.I) else "mentioned",
                "note": "Detected from query — use as context unless user asks to measure this deal forward",
            }

        measure_ref = not (historical and block_sale)
        if historical and block_sale:
            measure_ref = False

        precedents = []
        if historical:
            if sold == "CEN.NZ" or re.search(r"\b(contact|cen)\b", text, re.I):
                precedents = [
                    "Origin / Contact 2015",
                    "Z Energy / Infratil 2015",
                    "Air New Zealand 2013",
                    "Auckland Airport 2024",
                ]
            else:
                for name in (
                    "Z Energy / Infratil 2015",
                    "Origin / Contact 2015",
                    "Air New Zealand 2013",
                    "Auckland Airport 2024",
                ):
                    precedents.append(name)
            if not precedents:
                precedents = [
                    "Origin / Contact 2015",
                    "Z Energy / Infratil 2015",
                    "Air New Zealand 2013",
                ]

        comp = "historical_precedents" if historical else "general"
        if historical and ref:
            comp = "historical_precedents"

        outputs = []
        if re.search(r"\b1\s*month\b", text) or re.search(r"\b3\s*month", text):
            outputs = [
                "seller_T+1m",
                "seller_T+3m",
                "seller_T+6m",
                "sold_T+1m",
                "sold_T+3m",
                "sold_T+6m",
            ]

        return ResearchQueryAnalysis(
            comparison_type=comp,
            reference_event=ref,
            measure_forward_returns_for_reference=measure_ref,
            required_outputs=outputs,
            suggested_precedents=precedents[:6],
            raw={"source": "rule_based"},
        )

    @staticmethod
    def _format_history(messages: List[Dict], max_chars: int = 1500) -> str:
        parts = []
        total = 0
        for msg in messages[-4:]:
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = str(msg.get("content", ""))[:400]
            line = f"{role.upper()}: {content}"
            if total + len(line) > max_chars:
                break
            parts.append(line)
            total += len(line)
        return "\n".join(parts)
