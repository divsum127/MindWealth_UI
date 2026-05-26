"""
MindWealth Chatbot Agents
"""

from .intent_classifier import IntentClassifier, IntentResult, DataScopeHint
from .web_search_agent import WebSearchAgent, WebSearchResult, SearchResult
from .llm_router import LLMRouter, LLMRouteOutput
from .master_router import (
    MasterRouter,
    RouteDecision,
    ROUTE_INTERNAL,
    ROUTE_WEB_RAG,
    ROUTE_HYBRID,
    ROUTE_CONVERSATIONAL,
    ROUTE_DEEP_RESEARCH,
)
from .deep_research_gate import should_deep_research
from .orchestrator import ParallelOrchestrator, OrchestratorResult
from .synthesis_agent import SynthesisAgent

__all__ = [
    "IntentClassifier",
    "IntentResult",
    "DataScopeHint",
    "WebSearchAgent",
    "WebSearchResult",
    "SearchResult",
    "LLMRouter",
    "LLMRouteOutput",
    "MasterRouter",
    "RouteDecision",
    "ROUTE_INTERNAL",
    "ROUTE_WEB_RAG",
    "ROUTE_HYBRID",
    "ROUTE_CONVERSATIONAL",
    "ROUTE_DEEP_RESEARCH",
    "should_deep_research",
    "ParallelOrchestrator",
    "OrchestratorResult",
    "SynthesisAgent",
]
