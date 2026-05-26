"""
ResearchSubTaskExecutor — runs one subtask via internal, web, or hybrid paths.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from chatbot.config import (
    DEEP_RESEARCH_INTERNAL_TIMEOUT_SECONDS,
    DEEP_RESEARCH_WEB_MAX_QUERIES_PER_SUBTASK,
    DEEP_RESEARCH_WEB_MAX_RESULTS,
)

from chatbot.config import ENABLE_LLM_EVENT_DATE_EXTRACTION
from chatbot.tools.llm_event_date_extractor import extract_event_date_from_web

from .orchestrator import ParallelOrchestrator
from .price_data_agent import PriceDataAgent
from .research_types import EvidenceStore, ResearchSubTask, SubTaskEvidence
from .synthesis_agent import SynthesisAgent
from .web_search_agent import SearchResult, WebSearchAgent

logger = logging.getLogger(__name__)

_CURRENT_CEN_NOISE = re.compile(
    r"contact energy|may 2026|25 may|495\s*million|9\.25 per share|reduces contact stake",
    re.I,
)
_PRECEDENT_KEYWORDS = re.compile(
    r"z energy|zel\b|origin energy|origin\b|trustpower|genesis energy|air new zealand",
    re.I,
)


class ResearchSubTaskExecutor:
    def __init__(
        self,
        web_agent: Optional[WebSearchAgent],
        internal_fn: Callable[..., Tuple[Dict, Dict]],
        *,
        web_timeout: float = 45.0,
        internal_timeout: float = 60.0,
    ):
        self._web = web_agent
        self._internal_fn = internal_fn
        self._web_timeout = web_timeout
        self._internal_timeout = internal_timeout
        self._synthesis = SynthesisAgent()
        self._orchestrator = ParallelOrchestrator()
        self._price_agent = PriceDataAgent()

    def execute(
        self,
        subtask: ResearchSubTask,
        *,
        store: Optional[EvidenceStore] = None,
        assets: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        functions: Optional[List[str]] = None,
    ) -> Tuple[SubTaskEvidence, Dict[str, Any]]:
        mode = subtask.retrieval_mode
        logger.info(f"[DEEP_RESEARCH] Executing subtask {subtask.id} mode={mode}")
        t0 = time.monotonic()

        try:
            if mode == "price_data":
                evidence, detail = self._execute_price_data(subtask, store)
            elif mode == "web":
                evidence, detail = self._execute_web(subtask)
            elif mode == "internal":
                evidence, detail = self._execute_internal(
                    subtask,
                    assets=assets,
                    from_date=from_date,
                    to_date=to_date,
                    functions=functions,
                )
            else:
                evidence, detail = self._execute_hybrid(
                    subtask,
                    assets=assets,
                    from_date=from_date,
                    to_date=to_date,
                    functions=functions,
                )
            detail["elapsed_ms"] = round((time.monotonic() - t0) * 1000, 1)
            return evidence, detail
        except Exception as exc:
            logger.error(f"Subtask {subtask.id} failed: {exc}")
            inferred = None
            if mode == "price_data" and store:
                for dep_id in subtask.depends_on or []:
                    dep = store.get_entry(dep_id)
                    if dep and dep.inferred_event_date:
                        inferred = dep.inferred_event_date
                        break
            evidence = SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode=mode,
                success=False,
                error=str(exc),
                inferred_event_date=inferred,
                summary=f"Subtask failed: {exc}",
            )
            return evidence, {
                "error": str(exc),
                "inferred_event_date": inferred,
                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            }

    def _execute_price_data(
        self,
        subtask: ResearchSubTask,
        store: Optional[EvidenceStore],
    ) -> Tuple[SubTaskEvidence, Dict[str, Any]]:
        if store is None:
            return SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode="price_data",
                success=False,
                error="EvidenceStore required for price_data subtasks",
            ), {"price_data": {"error": "no store"}}
        return self._price_agent.run(subtask, store)

    def _execute_web(self, subtask: ResearchSubTask) -> Tuple[SubTaskEvidence, Dict[str, Any]]:
        if not self._web or not self._web.is_available:
            return SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode="web",
                success=False,
                error="Web search unavailable",
            ), {"web": {"error": "Web search unavailable"}}
        result = self._web.run_research(
            subtask.question,
            subtask.web_queries,
            temporal_scope=subtask.temporal_scope,
            max_results_per_query=DEEP_RESEARCH_WEB_MAX_RESULTS,
            max_queries=DEEP_RESEARCH_WEB_MAX_QUERIES_PER_SUBTASK,
            global_max_results=DEEP_RESEARCH_WEB_MAX_RESULTS * 3,
        )
        detail = {
            "web": {
                "queries_executed": result.search_queries_used,
                "per_query": getattr(result, "per_query", []) or [],
                "merged_result_count": len(result.results or []),
                "error": result.error,
            }
        }
        if not result.success:
            return SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode="web",
                success=False,
                error=result.error,
                web_queries_used=result.search_queries_used,
            ), detail

        filtered_results, filtered_out = self._filter_precedent_web_results(
            result.results or [], subtask
        )
        if filtered_results:
            formatted = WebSearchAgent._format_for_claude(
                subtask.question, filtered_results
            )
            sources = [r.url for r in filtered_results]
        else:
            formatted = result.formatted_context
            sources = result.sources
            filtered_results = result.results or []

        blob = formatted + "\n".join(
            (getattr(r, "content", "") or "")[:500] for r in filtered_results
        )
        source_dicts = [
            {
                "title": getattr(r, "title", "") or "",
                "url": getattr(r, "url", "") or "",
                "content": getattr(r, "content", "") or "",
            }
            for r in filtered_results
        ]
        extraction = extract_event_date_from_web(
            question=subtask.question,
            sources=source_dicts,
            text_blob=blob,
            precedent_name=subtask.precedent_name,
            seller_ticker=subtask.seller_ticker,
            sold_ticker=subtask.sold_ticker,
            use_llm=ENABLE_LLM_EVENT_DATE_EXTRACTION,
        )
        inferred_date = extraction.event_date
        inferred_seller = extraction.seller_ticker or subtask.seller_ticker
        inferred_sold = extraction.sold_ticker or subtask.sold_ticker
        if not extraction.seller_is_listed:
            inferred_seller = None

        facts = self._extract_snippet_facts_from_list(filtered_results)
        if inferred_date:
            facts.insert(
                0,
                f"Event date inferred ({extraction.source}): {inferred_date} — {extraction.reasoning}",
            )
        if inferred_seller:
            facts.insert(1, f"Seller ticker: {inferred_seller}")
        elif extraction.seller_name:
            facts.insert(1, f"Seller: {extraction.seller_name} (unlisted)")
        if inferred_sold:
            facts.insert(2, f"Sold ticker: {inferred_sold}")

        detail["web"]["filtered_out_count"] = filtered_out
        detail["web"]["inferred_event_date"] = inferred_date
        detail["web"]["event_date_extraction"] = extraction.to_dict()

        return SubTaskEvidence(
            subtask_id=subtask.id,
            question=subtask.question,
            retrieval_mode="web",
            success=True,
            summary=f"{len(filtered_results)} web sources collected",
            formatted_context=formatted,
            sources=sources,
            web_queries_used=result.search_queries_used,
            facts_extracted=facts,
            inferred_event_date=inferred_date,
            inferred_seller_ticker=inferred_seller,
            inferred_sold_ticker=inferred_sold,
            event_date_extraction=extraction.to_dict(),
        ), detail

    def _execute_internal(
        self,
        subtask: ResearchSubTask,
        *,
        assets: Optional[List[str]],
        from_date: Optional[str],
        to_date: Optional[str],
        functions: Optional[List[str]],
    ) -> Tuple[SubTaskEvidence, Dict[str, Any]]:
        scope = subtask.internal_scope or {}
        msg = subtask.question
        tickers = scope.get("tickers") or assets
        sig_types = scope.get("signal_types")
        if sig_types and isinstance(sig_types, list):
            selected = list(sig_types)
        else:
            selected = []

        fetched, meta = self._internal_fn(
            msg,
            selected_signal_types=selected,
            assets=tickers,
            from_date=from_date,
            to_date=to_date,
            functions=functions or scope.get("functions"),
            auto_extract_tickers=not tickers,
        )
        row_counts = {
            st: (len(df) if hasattr(df, "__len__") else 0)
            for st, df in (fetched or {}).items()
        }
        detail = {
            "internal": {
                "signal_types_loaded": list((fetched or {}).keys()),
                "row_counts": row_counts,
                "extraction_meta_keys": list(meta.keys()) if meta else [],
                "error": meta.get("error"),
            }
        }
        if meta.get("error"):
            return SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode="internal",
                success=False,
                error=str(meta.get("error")),
            ), detail
        formatted = self._format_internal_data(fetched, meta)
        return SubTaskEvidence(
            subtask_id=subtask.id,
            question=subtask.question,
            retrieval_mode="internal",
            success=bool(fetched),
            summary=f"Internal data: {list(fetched.keys()) if fetched else 'empty'}",
            formatted_context=formatted,
            facts_extracted=[f"Loaded signal types: {list(fetched.keys())}"] if fetched else [],
        ), detail

    def _execute_hybrid(
        self,
        subtask: ResearchSubTask,
        *,
        assets: Optional[List[str]],
        from_date: Optional[str],
        to_date: Optional[str],
        functions: Optional[List[str]],
    ) -> Tuple[SubTaskEvidence, Dict[str, Any]]:
        scope = subtask.internal_scope or {}
        tickers = scope.get("tickers") or assets
        sig_types = scope.get("signal_types") or []

        def web_fn():
            if not self._web or not self._web.is_available:
                return None
            return self._web.run_research(
                subtask.question,
                subtask.web_queries,
                temporal_scope=subtask.temporal_scope,
                max_results_per_query=DEEP_RESEARCH_WEB_MAX_RESULTS,
                max_queries=DEEP_RESEARCH_WEB_MAX_QUERIES_PER_SUBTASK,
            )

        def internal_fn():
            return self._internal_fn(
                subtask.question,
                selected_signal_types=list(sig_types) if sig_types else [],
                assets=tickers,
                from_date=from_date,
                to_date=to_date,
                functions=functions,
                auto_extract_tickers=not tickers,
            )

        orch = self._orchestrator.run(
            web_fn=web_fn,
            internal_fn=internal_fn,
            web_timeout=self._web_timeout,
            internal_timeout=self._internal_timeout,
        )
        prompt = self._synthesis.build_prompt(
            user_message=subtask.question,
            web_result=orch.web_result,
            signal_data=orch.signal_data,
            signal_metadata=orch.signal_metadata,
            web_failed=orch.web_failed,
            internal_failed=orch.internal_failed,
            web_error=orch.web_error,
            internal_error=orch.internal_error,
        )
        sources = []
        web_detail: Dict[str, Any] = {}
        if orch.web_result:
            if getattr(orch.web_result, "sources", None):
                sources = list(orch.web_result.sources)
            web_detail = {
                "queries_executed": getattr(orch.web_result, "search_queries_used", []) or [],
                "per_query": getattr(orch.web_result, "per_query", []) or [],
                "merged_result_count": len(getattr(orch.web_result, "results", []) or []),
            }
        internal_rows = {
            st: (len(df) if hasattr(df, "__len__") else 0)
            for st, df in (orch.signal_data or {}).items()
        }
        detail = {
            "hybrid": {
                "web_failed": orch.web_failed,
                "web_error": orch.web_error,
                "internal_failed": orch.internal_failed,
                "internal_error": orch.internal_error,
                "web": web_detail,
                "internal_row_counts": internal_rows,
            }
        }
        return SubTaskEvidence(
            subtask_id=subtask.id,
            question=subtask.question,
            retrieval_mode="hybrid",
            success=not (orch.web_failed and orch.internal_failed),
            summary="Hybrid subtask context assembled",
            formatted_context=prompt,
            sources=sources,
            web_queries_used=getattr(orch.web_result, "search_queries_used", None) or [],
        ), detail

    @staticmethod
    def _is_reference_context_subtask(subtask: ResearchSubTask) -> bool:
        q = (subtask.question or "").lower()
        return "context only" in q or (
            "brief context" in q and "current" in q
        )

    @classmethod
    def _filter_precedent_web_results(
        cls,
        results: List[SearchResult],
        subtask: ResearchSubTask,
    ) -> tuple[List[SearchResult], int]:
        if not subtask.precedent_name or cls._is_reference_context_subtask(subtask):
            return results, 0
        pn = (subtask.precedent_name or "").lower()
        if "contact 2026" in pn or "reference" in pn:
            return results, 0

        kept: List[SearchResult] = []
        removed = 0
        for r in results:
            text = f"{r.title} {r.content} {r.url}"
            has_noise = bool(_CURRENT_CEN_NOISE.search(text))
            has_precedent = bool(_PRECEDENT_KEYWORDS.search(text)) or any(
                tok in text.lower()
                for tok in pn.replace("/", " ").split()
                if len(tok) > 3
            )
            if has_noise and not has_precedent:
                removed += 1
                continue
            kept.append(r)

        if not kept and results:
            return results, 0
        return kept, removed

    @staticmethod
    def _extract_snippet_facts(result: Any) -> List[str]:
        return ResearchSubTaskExecutor._extract_snippet_facts_from_list(
            getattr(result, "results", []) or []
        )

    @staticmethod
    def _extract_snippet_facts_from_list(results: List[Any]) -> List[str]:
        facts = []
        for r in results:
            snippet = (getattr(r, "content", "") or "")[:200].strip()
            if snippet:
                facts.append(f"{getattr(r, 'title', '')}: {snippet}")
        return facts[:10]

    @staticmethod
    def _format_internal_data(fetched: Dict, meta: Dict) -> str:
        lines = ["=== INTERNAL SIGNAL DATA (subtask) ==="]
        for st, df in (fetched or {}).items():
            try:
                n = len(df) if hasattr(df, "__len__") else 0
                lines.append(f"--- {st}: {n} rows ---")
                if n > 0 and hasattr(df, "head"):
                    sample = df.head(15).to_string(max_cols=12)
                    if len(sample) > 4000:
                        sample = sample[:4000] + "\n..."
                    lines.append(sample)
            except Exception:
                lines.append(f"--- {st}: (could not serialize) ---")
        if meta.get("reasoning_by_signal_type"):
            lines.append(f"Extraction: {json.dumps(meta.get('reasoning_by_signal_type'), default=str)[:500]}")
        lines.append("=== END INTERNAL SIGNAL DATA ===")
        return "\n".join(lines)
