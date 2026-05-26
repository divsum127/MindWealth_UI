"""
ResearchPlanner — decomposes user queries into subtasks with retrieval modes.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Tuple

from chatbot.config import DEEP_RESEARCH_MIN_PRECEDENTS

from prompts.engine import RESEARCH_PLANNER_SYSTEM, RESEARCH_PLANNER_USER_TEMPLATE

from .research_query_analyzer import ResearchQueryAnalysis
from .research_types import (
    ResearchPlan,
    ResearchSubTask,
    RetrievalMode,
    TemporalScope,
    is_valid_subtask_question,
)

logger = logging.getLogger(__name__)

# NZ precedent → typical seller/sold tickers for fallback plans
_PRECEDENT_TICKERS: Dict[str, Tuple[str, str]] = {
    "Origin / Contact 2015": ("ORG.AX", "CEN.NZ"),
    "Origin Energy / Contact 2015": ("ORG.AX", "CEN.NZ"),
    "ORG.NZ": ("ORG.AX", "CEN.NZ"),
    "Z Energy / Infratil 2015": ("IFT.NZ", "ZEL.NZ"),
    "Z Energy": ("IFT.NZ", "ZEL.NZ"),
    "Trustpower": ("IFT.NZ", "TPW.NZ"),
    "Genesis Energy": ("IFT.NZ", "GNE.NZ"),
    "Genesis": ("IFT.NZ", "GNE.NZ"),
    "Meridian Energy": ("IFT.NZ", "MEL.NZ"),
    "Mercury NZ": ("IFT.NZ", "MCY.NZ"),
    "Air New Zealand 2013": (None, "AIR.NZ"),
    "Air New Zealand": (None, "AIR.NZ"),
    "Auckland Airport 2024": ("AUC", "AIA.NZ"),
}


class ResearchPlanner:
    def __init__(self, api_key: Optional[str], model: str = "gpt-4o-mini", max_subtasks: int = 8):
        self._model = model
        self._max_subtasks = max_subtasks
        self._client = None
        if api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
            except Exception as exc:
                logger.error(f"ResearchPlanner: OpenAI init failed: {exc}")

    @property
    def available(self) -> bool:
        return self._client is not None

    def plan(
        self,
        user_message: str,
        history_messages: Optional[List[Dict]] = None,
        query_analysis: Optional[ResearchQueryAnalysis] = None,
    ) -> Tuple[ResearchPlan, Optional[Dict]]:
        if query_analysis is None:
            from .research_query_analyzer import ResearchQueryAnalyzer

            query_analysis = ResearchQueryAnalyzer(None).analyze(user_message, history_messages)

        if not self._client:
            plan = self._fallback_plan(user_message, query_analysis)
            plan.query_analysis = query_analysis.to_dict()
            return plan, None

        history = self._format_history(history_messages or [])
        system = RESEARCH_PLANNER_SYSTEM.format(
            max_subtasks=self._max_subtasks,
            min_precedents=DEEP_RESEARCH_MIN_PRECEDENTS,
        )
        user_prompt = RESEARCH_PLANNER_USER_TEMPLATE.format(
            history=history or "(none)",
            query=user_message.strip(),
            query_analysis=query_analysis.format_for_planner(),
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=2000,
                temperature=0,
            )
            data = json.loads(response.choices[0].message.content.strip())
            plan = self._parse_plan(user_message, data, query_analysis)
            return plan, data
        except Exception as exc:
            logger.error(f"ResearchPlanner failed: {exc}")
            plan = self._fallback_plan(user_message, query_analysis)
            plan.query_analysis = query_analysis.to_dict()
            return plan, {"error": str(exc)}

    def parse_refinement_subtasks(
        self,
        data: dict,
        user_message: str,
        max_subtasks: int = 4,
    ) -> List[ResearchSubTask]:
        raw = data.get("refinement_subtasks") or []
        if not isinstance(raw, list):
            return []
        subtasks = []
        for i, item in enumerate(raw[:max_subtasks]):
            if not isinstance(item, dict):
                continue
            st = self._parse_subtask(item, f"ref{i+1}")
            if st is None:
                logger.warning(
                    "[DEEP_RESEARCH] Skipping invalid refinement subtask: %s",
                    item.get("question", item),
                )
                continue
            st.is_refinement = True
            subtasks.append(st)
        return subtasks

    def _parse_plan(
        self,
        user_message: str,
        data: dict,
        query_analysis: ResearchQueryAnalysis,
    ) -> ResearchPlan:
        summary = str(data.get("summary", "")).strip() or "Research plan"
        reasoning = str(data.get("reasoning", "")).strip()
        raw_tasks = data.get("subtasks") or []
        subtasks: List[ResearchSubTask] = []
        if isinstance(raw_tasks, list):
            for i, item in enumerate(raw_tasks[: self._max_subtasks]):
                if isinstance(item, dict):
                    st = self._parse_subtask(item, f"st{i+1}")
                    if st is not None:
                        subtasks.append(st)
        if not subtasks:
            return self._fallback_plan(user_message, query_analysis)
        return ResearchPlan(
            user_question=user_message,
            summary=summary,
            subtasks=subtasks,
            reasoning=reasoning,
            query_analysis=query_analysis.to_dict(),
        )

    def _parse_subtask(self, item: dict, default_id: str) -> Optional[ResearchSubTask]:
        question = str(item.get("question", "")).strip()
        if not is_valid_subtask_question(question):
            return None

        mode = str(item.get("retrieval_mode", "web")).lower()
        if mode not in ("internal", "web", "hybrid", "price_data"):
            mode = "web"
        ts = str(item.get("temporal_scope", "any")).lower()
        if ts not in ("historical", "recent", "any"):
            ts = "any"
        wq = item.get("web_queries") or []
        if isinstance(wq, list):
            wq = [str(q).strip() for q in wq if q and str(q).strip()][:4]
        else:
            wq = []
        dep = item.get("depends_on") or []
        if not isinstance(dep, list):
            dep = []
        scope = item.get("internal_scope")
        if scope is not None and not isinstance(scope, dict):
            scope = None

        offsets = item.get("price_offsets_months") or [1, 3, 6]
        if isinstance(offsets, list):
            offsets = [int(x) for x in offsets if isinstance(x, (int, float))][:6]
        else:
            offsets = [1, 3, 6]
        if not offsets:
            offsets = [1, 3, 6]

        event_date = item.get("event_date")
        if event_date is not None:
            event_date = str(event_date).strip() or None
            if event_date and event_date.lower() in ("null", "none", ""):
                event_date = None

        # Never trust planner-invented dates on price_data — web subtask must discover them
        if mode == "price_data" and dep:
            event_date = None

        return ResearchSubTask(
            id=str(item.get("id", default_id)).strip() or default_id,
            question=question,
            retrieval_mode=mode,  # type: ignore[arg-type]
            rationale=str(item.get("rationale", "")).strip(),
            success_criteria=str(item.get("success_criteria", "")).strip(),
            web_queries=wq,
            internal_scope=scope,
            depends_on=[str(d) for d in dep],
            temporal_scope=ts,  # type: ignore[arg-type]
            is_refinement=bool(item.get("is_refinement", False)),
            precedent_name=(str(item["precedent_name"]).strip() if item.get("precedent_name") else None),
            seller_ticker=(str(item["seller_ticker"]).strip() if item.get("seller_ticker") else None),
            sold_ticker=(str(item["sold_ticker"]).strip() if item.get("sold_ticker") else None),
            event_date=event_date,
            price_offsets_months=offsets,
        )

    def _fallback_plan(
        self,
        user_message: str,
        query_analysis: ResearchQueryAnalysis,
    ) -> ResearchPlan:
        """Rule-based two-phase plan when LLM planner unavailable."""
        if query_analysis.comparison_type == "historical_precedents":
            subtasks = self._historical_precedent_subtasks(query_analysis)
            if subtasks:
                return ResearchPlan(
                    user_question=user_message,
                    summary="Fallback: historical NZ block-sale precedents (web discovery + price_data)",
                    reasoning="Planner unavailable; rule-based precedent pairs",
                    subtasks=subtasks[: self._max_subtasks],
                    query_analysis=query_analysis.to_dict(),
                )

        return ResearchPlan(
            user_question=user_message,
            summary="Fallback: broad web research",
            reasoning="Planner unavailable",
            subtasks=[
                ResearchSubTask(
                    id="st1",
                    question=user_message[:300] if len(user_message) >= 12 else f"Research: {user_message}",
                    retrieval_mode="web",
                    rationale="Default web retrieval",
                    success_criteria="Relevant web snippets addressing the question",
                    web_queries=[user_message[:200]],
                    temporal_scope="any",
                )
            ],
            query_analysis=query_analysis.to_dict(),
        )

    def _historical_precedent_subtasks(
        self,
        query_analysis: ResearchQueryAnalysis,
    ) -> List[ResearchSubTask]:
        precedents = (query_analysis.suggested_precedents or [])[:DEEP_RESEARCH_MIN_PRECEDENTS + 2]
        if len(precedents) < DEEP_RESEARCH_MIN_PRECEDENTS:
            precedents = list(precedents) + [
                "Origin / Contact 2015",
                "Z Energy / Infratil 2015",
                "Air New Zealand 2013",
            ][:DEEP_RESEARCH_MIN_PRECEDENTS]

        subtasks: List[ResearchSubTask] = []
        for i, name in enumerate(precedents[:DEEP_RESEARCH_MIN_PRECEDENTS + 2]):
            if len(subtasks) >= self._max_subtasks - 1:
                break
            seller, sold = _PRECEDENT_TICKERS.get(name, ("IFT.NZ", None))
            web_queries = self._web_queries_for_precedent(name)
            web_id = f"st{i * 2 + 1}"
            price_id = f"st{i * 2 + 2}"
            subtasks.append(
                ResearchSubTask(
                    id=web_id,
                    question=f"Find historical block sale / divestment date for {name} (seller vs sold stock)",
                    retrieval_mode="web",
                    rationale="Discover event date before price computation",
                    success_criteria=f"Event date and parties for {name} block sale",
                    web_queries=web_queries,
                    temporal_scope="historical",
                    precedent_name=name,
                    seller_ticker=seller,
                    sold_ticker=sold,
                )
            )
            if len(subtasks) >= self._max_subtasks:
                break
            subtasks.append(
                ResearchSubTask(
                    id=price_id,
                    question=f"Compute T+1m/3m/6m seller vs sold prices after {name} block sale",
                    retrieval_mode="price_data",
                    rationale="yfinance post-event returns",
                    success_criteria="T0 and T+1m/3m/6m closes for seller and sold tickers",
                    depends_on=[web_id],
                    temporal_scope="historical",
                    precedent_name=name,
                    seller_ticker=seller,
                    sold_ticker=sold,
                    price_offsets_months=[1, 3, 6],
                )
            )

        if not query_analysis.measure_forward_returns_for_reference and query_analysis.reference_event:
            ref = query_analysis.reference_event
            note = ref.get("note") or "Current deal — context only"
            if len(subtasks) < self._max_subtasks:
                subtasks.append(
                    ResearchSubTask(
                        id=f"st{len(subtasks) + 1}",
                        question="Brief context on current reference block sale (no forward return measurement)",
                        retrieval_mode="web",
                        rationale="Reference event context only",
                        success_criteria="Announcement details; no T+Xm measurement required",
                        web_queries=[
                            "Infratil Contact Energy block sale May 2026 announcement",
                        ],
                        temporal_scope="recent",
                        seller_ticker=ref.get("seller_ticker"),
                        sold_ticker=ref.get("sold_ticker"),
                    )
                )
        return subtasks

    @staticmethod
    def _web_queries_for_precedent(name: str) -> List[str]:
        nl = name.lower()
        if "origin" in nl or "contact 2015" in nl:
            return [
                "Origin Energy sold Contact Energy block trade August 2015 Macquarie",
                "Origin Energy Contact Energy divestment 2015 announcement date",
            ]
        if "z energy" in nl:
            return [
                "Infratil Z Energy block trade October 2015 announcement date",
                "Infratil sold 20 percent Z Energy September 2015 book build",
            ]
        if "air new zealand" in nl or "air nz" in nl:
            return [
                "New Zealand government Air New Zealand block trade November 2013",
                "Crown sold Air New Zealand stake 2013 block trade date",
            ]
        if "auckland airport" in nl:
            return [
                "Auckland Council Auckland Airport block sale December 2024 date",
                "Auckland Airport AIA block trade 2024 announcement",
            ]
        return [
            f"{name} block sale announcement date NZX",
            f"{name} divestment block trade historical seller stock",
        ]

    @staticmethod
    def _format_history(messages: List[Dict], max_chars: int = 2500) -> str:
        parts = []
        total = 0
        for msg in messages[-6:]:
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = str(msg.get("content", ""))
            for marker in ("=== SIGNAL DATA", "=== WEB SEARCH", "=== EVIDENCE PACK"):
                if marker in content:
                    content = content.split(marker)[0].strip()
                    break
            line = f"{role.upper()}: {content[:600]}"
            if total + len(line) > max_chars:
                break
            parts.append(line)
            total += len(line)
        return "\n".join(parts)
