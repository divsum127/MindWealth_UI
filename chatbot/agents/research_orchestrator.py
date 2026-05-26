"""
ResearchOrchestrator — plan, execute subtasks, gap refinement, evidence store.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from chatbot.config import (
    DEEP_RESEARCH_MAX_ROUNDS,
    DEEP_RESEARCH_MAX_SUBTASKS,
    DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS,
)

from .price_data_agent import PriceDataAgent
from .research_gap_analyzer import ResearchGapAnalyzer
from .research_planner import ResearchPlanner
from .research_query_analyzer import ResearchQueryAnalyzer
from .research_subtask_executor import ResearchSubTaskExecutor
from .research_types import EvidenceStore, ResearchPlan, ResearchSubTask
from .web_search_agent import WebSearchAgent

if TYPE_CHECKING:
    from chatbot.deep_research_log import DeepResearchLogRecorder

logger = logging.getLogger(__name__)


class ResearchOrchestratorResult:
    def __init__(
        self,
        store: EvidenceStore,
        gaps_summary: str = "",
        elapsed_ms: float = 0.0,
        subtasks_executed: int = 0,
        refinement_rounds: int = 0,
    ):
        self.store = store
        self.gaps_summary = gaps_summary
        self.elapsed_ms = elapsed_ms
        self.subtasks_executed = subtasks_executed
        self.refinement_rounds = refinement_rounds


def _topological_order(subtasks: List[ResearchSubTask]) -> List[ResearchSubTask]:
    """Execute dependencies before dependents (web before price_data)."""
    by_id = {st.id: st for st in subtasks}
    in_degree: Dict[str, int] = {st.id: 0 for st in subtasks}
    dependents: Dict[str, List[str]] = {st.id: [] for st in subtasks}

    for st in subtasks:
        for dep in st.depends_on:
            if dep in by_id:
                in_degree[st.id] = in_degree.get(st.id, 0) + 1
                dependents.setdefault(dep, []).append(st.id)

    queue = [st.id for st in subtasks if in_degree.get(st.id, 0) == 0]
    ordered_ids: List[str] = []
    while queue:
        nid = queue.pop(0)
        ordered_ids.append(nid)
        for child in dependents.get(nid, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    for st in subtasks:
        if st.id not in ordered_ids:
            ordered_ids.append(st.id)

    return [by_id[i] for i in ordered_ids if i in by_id]


class ResearchOrchestrator:
    def __init__(
        self,
        planner: ResearchPlanner,
        gap_analyzer: ResearchGapAnalyzer,
        web_agent: Optional[WebSearchAgent],
        internal_fn: Callable[..., Tuple[Dict, Dict]],
        *,
        query_analyzer: Optional[ResearchQueryAnalyzer] = None,
        max_rounds: int = DEEP_RESEARCH_MAX_ROUNDS,
        total_timeout: float = DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS,
        on_step: Optional[Callable[[str, str], None]] = None,
        log_recorder: Optional["DeepResearchLogRecorder"] = None,
    ):
        self._planner = planner
        self._gap = gap_analyzer
        self._query_analyzer = query_analyzer
        self._executor = ResearchSubTaskExecutor(
            web_agent,
            internal_fn,
        )
        self._price_agent = PriceDataAgent()
        self._max_rounds = max_rounds
        self._total_timeout = total_timeout
        self._on_step = on_step
        self._log = log_recorder

    def run(
        self,
        user_message: str,
        history_messages: Optional[List[Dict]] = None,
        *,
        assets: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        functions: Optional[List[str]] = None,
    ) -> ResearchOrchestratorResult:
        t0 = time.monotonic()
        deadline = t0 + self._total_timeout

        def step(stage: str, detail: str) -> None:
            logger.info(f"[DEEP_RESEARCH] {stage}: {detail}")
            if self._on_step:
                try:
                    self._on_step(stage, detail)
                except Exception:
                    pass

        step("Query Analysis", "Parsing reference event vs historical precedents")
        analyzer = self._query_analyzer
        if analyzer is None:
            analyzer = ResearchQueryAnalyzer(None)
        query_analysis = analyzer.analyze(user_message, history_messages)
        if self._log:
            self._log.record_query_analysis(query_analysis.to_dict())

        step("Research Plan", "Decomposing your question into research subtasks")
        plan, raw_plan = self._planner.plan(
            user_message, history_messages, query_analysis=query_analysis
        )
        if len(plan.subtasks) > DEEP_RESEARCH_MAX_SUBTASKS:
            plan.subtasks = plan.subtasks[:DEEP_RESEARCH_MAX_SUBTASKS]
        if self._log:
            self._log.record_plan(plan, raw_planner_response=raw_plan)

        store = EvidenceStore(plan=plan)
        executed = 0
        gaps_summary = ""

        if self._log:
            self._log.start_execution_round(0, "initial")
        self._run_subtask_batch(
            plan.subtasks,
            store,
            step,
            deadline,
            assets=assets,
            from_date=from_date,
            to_date=to_date,
            functions=functions,
        )
        executed += len(plan.subtasks)
        try:
            retried = self._retry_failed_price_data(
                plan.subtasks,
                store,
                step,
                deadline,
                assets=assets,
                from_date=from_date,
                to_date=to_date,
                functions=functions,
            )
            executed += retried
        except Exception as exc:
            logger.error("[DEEP_RESEARCH] price_data retry batch failed: %s", exc)

        refinement_round = 0
        while refinement_round < self._max_rounds and time.monotonic() < deadline:
            step("Gap Analysis", f"Checking evidence (round {refinement_round + 1})")
            sufficient, gaps_summary, refinements, raw_gap = self._gap.analyze(
                store, user_message
            )
            if self._log:
                self._log.record_gap_analysis(
                    refinement_round,
                    sufficient=sufficient,
                    gaps_summary=gaps_summary,
                    refinement_count=len(refinements),
                    raw_response=raw_gap,
                    refinement_subtasks=refinements,
                )
            store.rounds_completed = refinement_round + 1
            if sufficient or not refinements:
                break
            refinement_round += 1
            step(
                "Refinement",
                f"Running {len(refinements)} follow-up searches for missing evidence",
            )
            if self._log:
                self._log.start_execution_round(refinement_round, "refinement")
            self._run_subtask_batch(
                refinements,
                store,
                step,
                deadline,
                assets=assets,
                from_date=from_date,
                to_date=to_date,
                functions=functions,
            )
            executed += len(refinements)

        elapsed_ms = (time.monotonic() - t0) * 1000
        return ResearchOrchestratorResult(
            store=store,
            gaps_summary=gaps_summary,
            elapsed_ms=elapsed_ms,
            subtasks_executed=executed,
            refinement_rounds=refinement_round,
        )

    def _run_subtask_batch(
        self,
        subtasks: List[ResearchSubTask],
        store: EvidenceStore,
        step: Callable[[str, str], None],
        deadline: float,
        **kwargs,
    ) -> None:
        ordered = _topological_order(subtasks)

        for i, st in enumerate(ordered):
            if time.monotonic() >= deadline:
                logger.warning("[DEEP_RESEARCH] Total timeout reached — stopping subtasks")
                break
            step(
                "Subtask",
                f"{i + 1}/{len(ordered)}: {st.id} ({st.retrieval_mode}) — {st.question[:80]}",
            )
            t_sub = time.monotonic()
            evidence, detail = self._executor.execute(st, store=store, **kwargs)
            elapsed_ms = (time.monotonic() - t_sub) * 1000
            store.add(evidence)
            if self._log:
                self._log.record_subtask_execution(
                    st,
                    evidence,
                    elapsed_ms=elapsed_ms,
                    execution_detail=detail,
                )

    def _retry_failed_price_data(
        self,
        subtasks: List[ResearchSubTask],
        store: EvidenceStore,
        step: Callable[[str, str], None],
        deadline: float,
        **kwargs,
    ) -> int:
        """Re-run price_data subtasks when dependent web now has inferred_event_date."""
        retried = 0
        by_id = {st.id: st for st in subtasks}
        for entry in list(store.entries):
            if entry.retrieval_mode != "price_data" or entry.success:
                continue
            st = by_id.get(entry.subtask_id)
            if not st:
                continue
            dep_date = None
            for dep_id in st.depends_on:
                dep_entry = store.get_entry(dep_id)
                if dep_entry and dep_entry.inferred_event_date:
                    dep_date = dep_entry.inferred_event_date
                    break
            if not dep_date:
                continue
            if time.monotonic() >= deadline:
                break
            step(
                "Price retry",
                f"Recomputing {st.id} with event date {dep_date}",
            )
            st.event_date = dep_date
            t_sub = time.monotonic()
            try:
                evidence, detail = self._price_agent.run(st, store)
            except Exception as exc:
                logger.error("[DEEP_RESEARCH] price_data retry failed %s: %s", st.id, exc)
                from .research_types import SubTaskEvidence

                evidence = SubTaskEvidence(
                    subtask_id=st.id,
                    question=st.question,
                    retrieval_mode="price_data",
                    success=False,
                    error=str(exc),
                )
                detail = {"price_data": {"error": str(exc)}, "retry": True}
            elapsed_ms = (time.monotonic() - t_sub) * 1000
            store.entries = [e for e in store.entries if e.subtask_id != st.id]
            store.add(evidence)
            if self._log:
                self._log.record_subtask_execution(
                    st,
                    evidence,
                    elapsed_ms=elapsed_ms,
                    execution_detail={**detail, "retry": True},
                )
            retried += 1
        return retried
