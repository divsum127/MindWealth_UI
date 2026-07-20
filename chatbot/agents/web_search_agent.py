"""
Web Search Agent — Tavily RAG pipeline for MindWealth chatbot.

Two-step flow:
  Step 1 – Query generation  : OpenAI gpt-4o-mini expands the user question
                                into 1-3 targeted search strings.
  Step 2 – Tavily search     : Execute each query, deduplicate by URL,
                                keep top-N by relevance score.

The formatted_context string produced by run() is ready to be injected
directly into a Claude prompt as an additional context block.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from prompts.engine import WEB_SEARCH_QUERY_GEN_PROMPT

logger = logging.getLogger(__name__)

try:
    from tavily import TavilyClient
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False
    logger.warning(
        "tavily-python not installed. Web search disabled. "
        "Run: pip install tavily-python"
    )


# ── Data classes ────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    score: float = 0.0


@dataclass
class WebSearchResult:
    query: str
    search_queries_used: List[str] = field(default_factory=list)
    results: List[SearchResult] = field(default_factory=list)
    formatted_context: str = ""
    sources: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    # Per-query Tavily breakdown (deep research logs)
    per_query: List[Dict[str, Any]] = field(default_factory=list)


# ── Agent ───────────────────────────────────────────────────────────────────────

class WebSearchAgent:
    """
    Web RAG agent backed by Tavily.

    Usage:
        agent = WebSearchAgent(tavily_api_key="tvly-...", openai_api_key="sk-...")
        result = agent.run(user_query="What did Apple announce today?")
        # inject result.formatted_context into Claude prompt
    """

    _QUERY_GEN_PROMPT = WEB_SEARCH_QUERY_GEN_PROMPT
    QUERY_GEN_PROMPT = WEB_SEARCH_QUERY_GEN_PROMPT

    def __init__(
        self,
        tavily_api_key: str,
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4o-mini",
        max_results: int = 3,
        max_chars_per_result: int = 1500,
        min_relevance_score: float = 0.3,
    ):
        self.max_results = max_results
        self.max_chars_per_result = max_chars_per_result
        self.min_relevance_score = min_relevance_score

        # Tavily client
        self._tavily: Optional[TavilyClient] = None
        if _TAVILY_AVAILABLE and tavily_api_key:
            try:
                self._tavily = TavilyClient(api_key=tavily_api_key)
                logger.info("WebSearchAgent: Tavily client initialized")
            except Exception as exc:
                logger.error(f"WebSearchAgent: Tavily init failed: {exc}")

        # OpenAI client for query generation
        self._openai = None
        self._openai_model = openai_model
        if openai_api_key:
            try:
                from openai import OpenAI
                self._openai = OpenAI(api_key=openai_api_key)
                logger.info("WebSearchAgent: OpenAI client initialized for query generation")
            except Exception as exc:
                logger.warning(f"WebSearchAgent: OpenAI init failed: {exc}")

    @property
    def is_available(self) -> bool:
        """True if Tavily client is ready."""
        return self._tavily is not None

    # ── Public API ──────────────────────────────────────────────────────────────

    def run(
        self,
        user_query: str,
        search_queries: Optional[List[str]] = None,
        context: str = "",
    ) -> WebSearchResult:
        """
        Execute web search and return formatted context for Claude.

        Args:
            user_query:     Original user question (used for fallback query).
            search_queries: Pre-generated queries from the router/classifier.
                            If None, generates them with OpenAI.
            context:        Short text from recent conversation turns.

        Returns:
            WebSearchResult — formatted_context is ready to inject into Claude prompt.
        """
        if not self.is_available:
            return WebSearchResult(
                query=user_query,
                success=False,
                error=(
                    "Tavily not available. "
                    "Install tavily-python and set TAVILY_API_KEY in .env or secrets.toml."
                ),
            )

        # Step 1 – generate queries if not pre-supplied
        queries = search_queries if search_queries else self._generate_queries(user_query, context)
        queries = [q for q in queries if q][:3]  # cap at 3
        if not queries:
            queries = [user_query]

        logger.info(f"WebSearchAgent: running {len(queries)} query/-ies: {queries}")

        # Step 2 – execute searches and collect results
        all_results: List[SearchResult] = []
        for q in queries:
            all_results.extend(self._search(q))

        # Deduplicate by URL, keep highest score
        seen: Dict[str, SearchResult] = {}
        for r in all_results:
            if r.url not in seen or r.score > seen[r.url].score:
                seen[r.url] = r

        # Filter by relevance, sort, keep top N
        all_sorted = sorted(seen.values(), key=lambda x: x.score, reverse=True)
        filtered = [
            r for r in all_sorted if r.score >= self.min_relevance_score
        ][: self.max_results]

        # If nothing passes threshold, use top-N unfiltered (Tavily scores vary by topic)
        if not filtered and all_sorted:
            logger.warning(
                f"WebSearchAgent: no results >= {self.min_relevance_score}; "
                f"using top {self.max_results} by raw score"
            )
            filtered = all_sorted[: self.max_results]

        if not filtered:
            return WebSearchResult(
                query=user_query,
                search_queries_used=queries,
                success=False,
                error="Tavily returned no usable results for these queries.",
            )

        formatted = self._format_for_claude(user_query, filtered)

        return WebSearchResult(
            query=user_query,
            search_queries_used=queries,
            results=filtered,
            formatted_context=formatted,
            sources=[r.url for r in filtered],
            success=True,
        )

    def run_research(
        self,
        subtask_question: str,
        search_queries: List[str],
        *,
        temporal_scope: str = "any",
        max_results_per_query: int = 8,
        max_queries: int = 4,
        global_max_results: int = 25,
        search_depth: str = "advanced",
    ) -> WebSearchResult:
        """
        Deep-research profile: more queries, advanced Tavily depth, higher result cap.
        Skips recency ``days=`` filter when temporal_scope is historical.
        """
        if not self.is_available:
            return WebSearchResult(
                query=subtask_question,
                success=False,
                error="Tavily not available for deep research.",
            )

        queries = [q.strip() for q in search_queries if q.strip()][:max_queries]
        if not queries:
            queries = [subtask_question[:200]]

        historical = temporal_scope == "historical"
        logger.info(
            f"WebSearchAgent.run_research: {len(queries)} queries, "
            f"depth={search_depth}, historical={historical}"
        )

        from chatbot.config import DEEP_RESEARCH_LOG_MAX_CONTENT_CHARS

        all_results: List[SearchResult] = []
        per_query_log: List[Dict[str, Any]] = []
        for q in queries:
            batch = self._search(
                q,
                max_results=max_results_per_query,
                search_depth=search_depth,
                apply_recency=not historical,
            )
            all_results.extend(batch)
            per_query_log.append({
                "query": q,
                "search_depth": search_depth,
                "temporal_scope": temporal_scope,
                "apply_recency_days_filter": not historical,
                "result_count": len(batch),
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "score": r.score,
                        "content": (
                            r.content[:DEEP_RESEARCH_LOG_MAX_CONTENT_CHARS]
                            + ("...(truncated)" if len(r.content) > DEEP_RESEARCH_LOG_MAX_CONTENT_CHARS else "")
                        ),
                    }
                    for r in batch
                ],
            })

        seen: Dict[str, SearchResult] = {}
        for r in all_results:
            if r.url not in seen or r.score > seen[r.url].score:
                seen[r.url] = r

        all_sorted = sorted(seen.values(), key=lambda x: x.score, reverse=True)
        filtered = [
            r for r in all_sorted if r.score >= self.min_relevance_score
        ][:global_max_results]
        if not filtered and all_sorted:
            filtered = all_sorted[:global_max_results]

        if not filtered:
            return WebSearchResult(
                query=subtask_question,
                search_queries_used=queries,
                success=False,
                error="No usable research results from Tavily.",
                per_query=per_query_log,
            )

        formatted = self._format_for_claude(subtask_question, filtered)
        return WebSearchResult(
            query=subtask_question,
            search_queries_used=queries,
            results=filtered,
            formatted_context=formatted,
            sources=[r.url for r in filtered],
            success=True,
            per_query=per_query_log,
        )

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _generate_queries(self, user_query: str, context: str) -> List[str]:
        """Use OpenAI to generate targeted search queries from the user question."""
        if not self._openai:
            return [user_query]

        prompt = self._QUERY_GEN_PROMPT.format(
            user_query=user_query,
            context=context[:500] if context else "(none)",
        )
        try:
            response = self._openai.chat.completions.create(
                model=self._openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=150,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            if "```" in raw:
                raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
            queries = json.loads(raw)
            if isinstance(queries, list) and queries:
                logger.info(f"WebSearchAgent: generated queries: {queries}")
                return [str(q) for q in queries[:3]]
        except Exception as exc:
            logger.warning(f"WebSearchAgent: query generation failed: {exc}")

        return [user_query]

    @staticmethod
    def _detect_recency_window(query: str) -> Optional[int]:
        """
        Parse the query for temporal keywords and return a recency window in days,
        or None for historical / no-temporal queries.

        Returned value is passed as ``days=`` to Tavily to filter out stale results.

        Mapping:
          7  — "today", "right now", "this week", "breaking", "breaking news"
          30 — "latest", "recent", "current", "now", "this month"
          90 — "this year", "2026"
          None — no temporal keyword detected, or explicit historical query
        """
        q = query.lower()
        if any(kw in q for kw in ("today", "right now", "this week", "breaking")):
            return 7
        if any(kw in q for kw in ("latest", "recent", "current", "this month")):
            return 30
        if any(kw in q for kw in ("this year", "2026")):
            return 90
        return None

    def _search(
        self,
        query: str,
        *,
        max_results: Optional[int] = None,
        search_depth: str = "basic",
        apply_recency: bool = True,
    ) -> List[SearchResult]:
        """Run a single Tavily search and return parsed SearchResult list."""
        try:
            days = self._detect_recency_window(query) if apply_recency else None
            kwargs: Dict[str, Any] = dict(
                query=query,
                search_depth=search_depth,
                max_results=max_results if max_results is not None else self.max_results,
                include_answer=False,
            )
            if days is not None:
                kwargs["days"] = days
                logger.info(f"WebSearchAgent: recency filter → days={days} for query '{query[:60]}'")
            import time
            start = time.perf_counter()
            response = self._tavily.search(**kwargs)
            results = []
            for item in response.get("results", []):
                content = (item.get("content") or "").strip()
                if len(content) > self.max_chars_per_result:
                    content = content[: self.max_chars_per_result] + "..."
                results.append(
                    SearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        content=content,
                        score=float(item.get("score", 0.0)),
                    )
                )
            logger.info(f"WebSearchAgent: '{query}' → {len(results)} results")
            try:
                from api.services.integration_health_store import record_tavily_search
                record_tavily_search(
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    success=True,
                    query=query,
                )
            except Exception:
                pass
            return results
        except Exception as exc:
            logger.error(f"WebSearchAgent: Tavily search error for '{query}': {exc}")
            return []

    @staticmethod
    def _format_for_claude(user_query: str, results: List[SearchResult]) -> str:
        """Format results as a context block ready for Claude."""
        lines = [
            "=== WEB SEARCH RESULTS ===",
            f"Original question: {user_query}",
            "",
        ]
        for i, r in enumerate(results, 1):
            lines += [
                f"[Source {i}] {r.title}",
                f"URL: {r.url}",
                f"Relevance: {r.score:.2f}",
                r.content,
                "",
            ]
        lines += [
            "=== END WEB SEARCH RESULTS ===",
            "",
            (
                "IMPORTANT: When citing information from the web results above, "
                "use [Source N] tags (e.g. [Source 1]) to indicate the source of each claim. "
                "Do not fabricate information not present in the sources."
            ),
        ]
        return "\n".join(lines)
