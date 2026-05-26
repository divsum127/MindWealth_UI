"""
Master Router (RouterV2) for MindWealth Chatbot.

Primary path: LLMRouter — one OpenAI call decides:
  • conversational_only → history only
  • needs_web_search + needs_internal_signal_data → HYBRID (Tavily + smart_query)
  • needs_web_search only → WEB_RAG
  • needs_internal_signal_data only → INTERNAL

Fallback path (when LLM_ROUTER_ENABLED=false): IntentClassifier keyword / LLM intent routing.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .intent_classifier import (
    IntentClassifier,
    IntentResult,
    DataScopeHint,
    INTENT_CONVERSATIONAL,
    INTENT_WEB_QUERY,
    INTENT_SIGNAL_LOOKUP,
)
from .llm_router import LLMRouter, LLMRouteOutput
from .web_search_agent import WebSearchAgent, WebSearchResult

logger = logging.getLogger(__name__)

ROUTE_INTERNAL = "INTERNAL"
ROUTE_WEB_RAG = "WEB_RAG"
ROUTE_HYBRID = "HYBRID"
ROUTE_CONVERSATIONAL = "CONVERSATIONAL"
ROUTE_DEEP_RESEARCH = "DEEP_RESEARCH"


@dataclass
class RouteDecision:
    route: str
    intent_result: IntentResult
    web_search_result: Optional[WebSearchResult] = None
    llm_router_reasoning: Optional[str] = None
    # For HYBRID route: web search queries to be executed in parallel by the
    # Orchestrator rather than blocking here in the router.
    pending_web_search_queries: Optional[List[str]] = None

    @property
    def used_web_search(self) -> bool:
        return self.web_search_result is not None and self.web_search_result.success


def _intent_from_llm(llm: LLMRouteOutput) -> IntentResult:
    """Map LLMRouteOutput → IntentResult for UI badges and legacy fields."""
    hint = DataScopeHint()

    if llm.conversational_only:
        return IntentResult(
            primary_intent=INTENT_CONVERSATIONAL,
            confidence=0.92,
            is_hybrid=False,
            secondary_intent=None,
            reasoning=llm.reasoning or "LLM router: conversational",
            data_scope_hint=hint,
            classified_by="llm_router",
        )

    if llm.needs_web_search and llm.needs_internal_signal_data:
        return IntentResult(
            primary_intent=INTENT_SIGNAL_LOOKUP,
            confidence=0.88,
            is_hybrid=True,
            secondary_intent=INTENT_WEB_QUERY,
            reasoning=llm.reasoning or "LLM router: hybrid",
            data_scope_hint=hint,
            classified_by="llm_router",
            web_search_queries=llm.search_queries,
        )

    if llm.needs_web_search:
        return IntentResult(
            primary_intent=INTENT_WEB_QUERY,
            confidence=0.88,
            is_hybrid=False,
            secondary_intent=None,
            reasoning=llm.reasoning or "LLM router: web only",
            data_scope_hint=hint,
            classified_by="llm_router",
            web_search_queries=llm.search_queries,
        )

    return IntentResult(
        primary_intent=INTENT_SIGNAL_LOOKUP,
        confidence=0.85,
        is_hybrid=False,
        secondary_intent=None,
        reasoning=llm.reasoning or "LLM router: internal signals",
        data_scope_hint=hint,
        classified_by="llm_router",
    )


class MasterRouter:
    def __init__(
        self,
        classifier: IntentClassifier,
        web_agent: Optional[WebSearchAgent] = None,
        enable_web_search: bool = True,
        llm_router: Optional[LLMRouter] = None,
        use_llm_router: bool = True,
    ):
        self.classifier = classifier
        self.web_agent = web_agent
        self.enable_web_search = enable_web_search and (web_agent is not None)
        self.llm_router = llm_router
        self.use_llm_router = use_llm_router and (
            llm_router is not None and llm_router.available
        )

        if use_llm_router and llm_router and not llm_router.available:
            logger.warning(
                "MasterRouter: LLM router requested but OpenAI client unavailable — "
                "using intent-classifier fallback"
            )

    def route(
        self,
        user_message: str,
        history: Optional[List[Dict]] = None,
    ) -> RouteDecision:
        history = history or []

        if self.use_llm_router and self.llm_router and self.llm_router.available:
            return self._route_with_llm(user_message, history)

        return self._route_legacy(user_message, history)

    def _route_with_llm(
        self,
        user_message: str,
        history: List[Dict],
    ) -> RouteDecision:
        assert self.llm_router is not None
        llm_out = self.llm_router.route(user_message, history_messages=history)
        intent = _intent_from_llm(llm_out)

        logger.info(
            f"[ROUTER/llm] conv={llm_out.conversational_only} "
            f"internal={llm_out.needs_internal_signal_data} "
            f"web={llm_out.needs_web_search}"
        )

        if intent.primary_intent == INTENT_CONVERSATIONAL:
            return RouteDecision(
                route=ROUTE_CONVERSATIONAL,
                intent_result=intent,
                llm_router_reasoning=llm_out.reasoning,
            )

        if llm_out.needs_web_search:
            if llm_out.needs_internal_signal_data:
                # HYBRID: do NOT run web search here — pass the pending queries so
                # the ParallelOrchestrator can execute web search and internal fetch
                # concurrently.  Running web search here would block the router and
                # prevent parallelism.
                logger.info(
                    "[ROUTER/llm] HYBRID detected — deferring web search to Orchestrator"
                )
                return RouteDecision(
                    route=ROUTE_HYBRID,
                    intent_result=intent,
                    web_search_result=None,
                    pending_web_search_queries=llm_out.search_queries or [],
                    llm_router_reasoning=llm_out.reasoning,
                )
            # WEB_RAG only (no internal data needed) — run web search now; no
            # parallelism benefit since there is no concurrent internal fetch.
            web_result = self._run_web_search(user_message, intent, history)
            return RouteDecision(
                route=ROUTE_WEB_RAG,
                intent_result=intent,
                web_search_result=web_result,
                llm_router_reasoning=llm_out.reasoning,
            )

        return RouteDecision(
            route=ROUTE_INTERNAL,
            intent_result=intent,
            llm_router_reasoning=llm_out.reasoning,
        )

    def _route_legacy(
        self,
        user_message: str,
        history: List[Dict],
    ) -> RouteDecision:
        intent = self.classifier.classify(
            user_message,
            last_two_turns=history[-4:],
        )

        logger.info(
            f"[ROUTER/legacy] intent={intent.primary_intent} "
            f"confidence={intent.confidence:.2f} hybrid={intent.is_hybrid}"
        )

        if intent.primary_intent == INTENT_CONVERSATIONAL:
            return RouteDecision(route=ROUTE_CONVERSATIONAL, intent_result=intent)

        if intent.primary_intent == INTENT_WEB_QUERY and not intent.is_hybrid:
            web_result = self._run_web_search(user_message, intent, history)
            return RouteDecision(
                route=ROUTE_WEB_RAG,
                intent_result=intent,
                web_search_result=web_result,
            )

        if intent.is_hybrid and intent.secondary_intent == INTENT_WEB_QUERY:
            web_result = self._run_web_search(user_message, intent, history)
            return RouteDecision(
                route=ROUTE_HYBRID,
                intent_result=intent,
                web_search_result=web_result,
            )

        return RouteDecision(route=ROUTE_INTERNAL, intent_result=intent)

    def _run_web_search(
        self,
        user_message: str,
        intent: IntentResult,
        history: List[Dict],
    ) -> Optional[WebSearchResult]:
        if not self.enable_web_search or self.web_agent is None:
            logger.info("[ROUTER] Web search disabled or Tavily not configured")
            return None

        context = ""
        for msg in reversed(history[-6:]):
            if msg.get("role") == "assistant":
                context = str(msg.get("content", ""))[:400]
                break

        queries = intent.web_search_queries
        result = self.web_agent.run(
            user_query=user_message,
            search_queries=queries,
            context=context,
        )

        if not result.success:
            logger.warning(f"[ROUTER] Web search failed: {result.error}")
        else:
            logger.info(
                f"[ROUTER] Web search OK — {len(result.results)} results "
                f"queries={result.search_queries_used}"
            )

        return result
