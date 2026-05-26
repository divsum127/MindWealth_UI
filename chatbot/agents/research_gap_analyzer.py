"""
ResearchGapAnalyzer — decides if refinement subtasks are needed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from prompts.engine import RESEARCH_GAP_ANALYSIS_PROMPT

from chatbot.config import ENABLE_LLM_EVENT_DATE_EXTRACTION
from chatbot.tools.event_date_extractor import extract_event_dates
from chatbot.tools.llm_event_date_extractor import extract_event_date_from_web

from .research_planner import ResearchPlanner
from .research_types import EvidenceStore, ResearchSubTask

logger = logging.getLogger(__name__)

_FORWARD_MONTH_RE = re.compile(
    r"\b(1|3|6)\s*month|t\+1m|t\+3m|t\+6m|share price.*month",
    re.I,
)
_REFERENCE_CEN_RE = re.compile(
    r"\b(contact|cen\.nz|cen\b|may\s*25|may\s*2026|2026)\b",
    re.I,
)


class ResearchGapAnalyzer:
    def __init__(self, api_key: Optional[str], model: str = "gpt-4o-mini", max_refinement: int = 4):
        self._model = model
        self._max_refinement = max_refinement
        self._client = None
        self._planner_parser = ResearchPlanner(api_key=api_key, model=model)
        if api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
            except Exception as exc:
                logger.error(f"ResearchGapAnalyzer: OpenAI init failed: {exc}")

    def analyze(
        self,
        store: EvidenceStore,
        user_message: str,
    ) -> Tuple[bool, str, List[ResearchSubTask], Optional[Dict]]:
        """
        Returns (sufficient, gaps_summary, refinement_subtasks, raw_response).
        """
        query_analysis = getattr(store.plan, "query_analysis", None) or {}

        if not self._client:
            refinements = self._synthetic_price_data_refinements(store)
            if refinements:
                return False, "Retrying price_data with inferred event dates", refinements, None
            return True, "Gap analyzer unavailable — proceeding to synthesis", [], None

        qa_json = json.dumps(query_analysis, indent=2)
        prompt = RESEARCH_GAP_ANALYSIS_PROMPT.format(
            user_question=user_message,
            plan_summary=store.plan.summary,
            evidence=store.format_for_gap_analysis(),
            max_refinement_subtasks=self._max_refinement,
            query_analysis=qa_json,
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_completion_tokens=800,
                temperature=0,
            )
            data = json.loads(response.choices[0].message.content.strip())
            sufficient = bool(data.get("sufficient", True))
            gaps = str(data.get("gaps_summary", "")).strip()
            refinements = self._planner_parser.parse_refinement_subtasks(
                data, user_message, self._max_refinement
            )
            refinements = self._filter_refinements(refinements, query_analysis, store)
            if not refinements and not sufficient:
                refinements = self._synthetic_price_data_refinements(store)
            logger.info(
                f"[DEEP_RESEARCH] Gap analysis: sufficient={sufficient}, "
                f"refinements={len(refinements)}"
            )
            return sufficient, gaps, refinements, data
        except Exception as exc:
            logger.error(f"ResearchGapAnalyzer failed: {exc}")
            return True, f"Gap analysis error: {exc}", [], {"error": str(exc)}

    def _filter_refinements(
        self,
        refinements: List[ResearchSubTask],
        query_analysis: Dict[str, Any],
        store: EvidenceStore,
    ) -> List[ResearchSubTask]:
        measure_ref = bool(query_analysis.get("measure_forward_returns_for_reference", True))
        out: List[ResearchSubTask] = []
        seen_ids: set = set()

        for st in refinements:
            if self._is_forbidden_reference_refinement(st, measure_ref):
                logger.warning(
                    "[DEEP_RESEARCH] Dropped forbidden refinement: %s", st.question[:80]
                )
                continue
            upgraded = self._upgrade_to_price_data_if_needed(st, store)
            if upgraded.id in seen_ids:
                continue
            seen_ids.add(upgraded.id)
            out.append(upgraded)
        return out[: self._max_refinement]

    @staticmethod
    def _is_forbidden_reference_refinement(
        st: ResearchSubTask,
        measure_ref: bool,
    ) -> bool:
        if measure_ref:
            return False
        q = st.question or ""
        if st.retrieval_mode != "web":
            return False
        if not _FORWARD_MONTH_RE.search(q):
            return False
        return bool(_REFERENCE_CEN_RE.search(q))

    @staticmethod
    def _upgrade_to_price_data_if_needed(
        st: ResearchSubTask,
        store: EvidenceStore,
    ) -> ResearchSubTask:
        q = (st.question or "").lower()
        if st.retrieval_mode == "price_data":
            return st
        if not _FORWARD_MONTH_RE.search(q):
            return st
        dates = extract_event_dates(q)
        if not dates:
            blob = q
            for e in store.entries:
                if e.inferred_event_date:
                    dates.append(e.inferred_event_date)
            for e in store.entries:
                blob += " " + (e.formatted_context or "")[:2000]
            resolved = extract_event_date_from_web(
                question=st.question,
                sources=[],
                text_blob=blob,
                precedent_name=st.precedent_name,
                sold_ticker=st.sold_ticker,
                seller_ticker=st.seller_ticker,
                use_llm=ENABLE_LLM_EVENT_DATE_EXTRACTION,
            )
            if resolved.event_date:
                dates = [resolved.event_date]
        if not dates:
            return st
        event_date = sorted(dates)[0] if len(dates) == 1 else dates[0]
        for d in dates:
            if d < "2024-01-01":
                event_date = d
                break
        st.retrieval_mode = "price_data"  # type: ignore[assignment]
        st.event_date = event_date
        st.web_queries = []
        if not st.seller_ticker and st.precedent_name:
            pn = st.precedent_name.lower()
            if "air" in pn:
                st.seller_ticker = None
            elif "origin" in pn:
                st.seller_ticker = "ORG.AX"
            else:
                st.seller_ticker = "IFT.NZ"
        return st

    @staticmethod
    def _synthetic_price_data_refinements(store: EvidenceStore) -> List[ResearchSubTask]:
        """Build price_data refinements when web has dates but price_data failed."""
        refinements: List[ResearchSubTask] = []
        plan_by_id = {st.id: st for st in store.plan.subtasks}
        for entry in store.entries:
            if entry.retrieval_mode != "price_data" or entry.success:
                continue
            st = plan_by_id.get(entry.subtask_id)
            if not st:
                continue
            dep_date = None
            dep_id = None
            for did in st.depends_on:
                dep_entry = store.get_entry(did)
                if dep_entry and dep_entry.inferred_event_date:
                    dep_date = dep_entry.inferred_event_date
                    dep_id = did
                    break
            if not dep_date:
                continue
            refinements.append(
                ResearchSubTask(
                    id=f"{st.id}_retry",
                    question=f"Compute T+1m/3m/6m for {st.precedent_name or st.id} from {dep_date}",
                    retrieval_mode="price_data",
                    rationale="Retry with inferred event date from web discovery",
                    success_criteria="T0 and T+1m/3m/6m closes",
                    depends_on=[dep_id] if dep_id else st.depends_on,
                    temporal_scope="historical",
                    precedent_name=st.precedent_name,
                    seller_ticker=st.seller_ticker,
                    sold_ticker=st.sold_ticker,
                    event_date=None,
                    price_offsets_months=st.price_offsets_months or [1, 3, 6],
                    is_refinement=True,
                )
            )
        return refinements[:4]
