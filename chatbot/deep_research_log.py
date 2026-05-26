"""
Structured JSON logs for Deep Research runs — one file per query: ``dprsh_<uuid>.json``.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .config import DEEP_RESEARCH_LOGS_DIR

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _subtask_to_dict(st: Any) -> Dict[str, Any]:
    return {
        "id": st.id,
        "question": st.question,
        "retrieval_mode": st.retrieval_mode,
        "rationale": st.rationale,
        "success_criteria": st.success_criteria,
        "web_queries": list(st.web_queries or []),
        "internal_scope": st.internal_scope,
        "depends_on": list(st.depends_on or []),
        "temporal_scope": st.temporal_scope,
        "is_refinement": bool(st.is_refinement),
        "precedent_name": getattr(st, "precedent_name", None),
        "seller_ticker": getattr(st, "seller_ticker", None),
        "sold_ticker": getattr(st, "sold_ticker", None),
        "event_date": getattr(st, "event_date", None),
        "price_offsets_months": list(getattr(st, "price_offsets_months", None) or []),
    }


def _search_results_to_dict(results: List[Any], max_content_chars: int) -> List[Dict[str, Any]]:
    out = []
    for r in results or []:
        content = (getattr(r, "content", "") or "")
        if len(content) > max_content_chars:
            content = content[:max_content_chars] + "...(truncated)"
        out.append({
            "title": getattr(r, "title", ""),
            "url": getattr(r, "url", ""),
            "score": float(getattr(r, "score", 0.0)),
            "content": content,
        })
    return out


class DeepResearchLogRecorder:
    """Accumulates a structured audit log for one DEEP_RESEARCH invocation."""

    def __init__(
        self,
        *,
        session_id: str,
        user_message: str,
        log_id: Optional[str] = None,
    ):
        self.log_id = log_id or f"dprsh_{uuid4().hex}"
        self.session_id = session_id
        self.created_at = _utc_now()
        self._payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "log_id": self.log_id,
            "created_at": self.created_at,
            "session_id": session_id,
            "route": "DEEP_RESEARCH",
            "gate": {},
            "input": {"user_message": user_message},
            "plan": {},
            "execution": {"rounds": [], "gap_analyses": []},
            "synthesis": {},
            "outcome": {},
            "engine_log_lines": [],
        }

    def set_gate(self, gate_info: Dict[str, Any]) -> None:
        self._payload["gate"] = gate_info

    def set_input_context(
        self,
        *,
        assets: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        functions: Optional[List[str]] = None,
        query_kind: Optional[str] = None,
        deep_research_enabled: bool = False,
    ) -> None:
        self._payload["input"].update({
            "assets": assets,
            "from_date": from_date,
            "to_date": to_date,
            "functions": functions,
            "query_kind": query_kind,
            "deep_research_enabled": deep_research_enabled,
        })

    def record_query_analysis(self, query_analysis: Dict[str, Any]) -> None:
        self._payload["query_analysis"] = query_analysis

    def record_plan(self, plan: Any, *, raw_planner_response: Optional[Dict] = None) -> None:
        self._payload["plan"] = {
            "summary": plan.summary,
            "reasoning": plan.reasoning,
            "user_question": plan.user_question,
            "subtask_count": len(plan.subtasks),
            "subtasks": [_subtask_to_dict(st) for st in plan.subtasks],
            "query_analysis": getattr(plan, "query_analysis", None),
            "raw_planner_response": raw_planner_response,
        }

    def start_execution_round(self, round_index: int, round_type: str) -> None:
        self._payload["execution"]["rounds"].append({
            "round_index": round_index,
            "round_type": round_type,
            "started_at": _utc_now(),
            "subtasks": [],
        })

    def _current_round(self) -> Dict[str, Any]:
        rounds = self._payload["execution"]["rounds"]
        if not rounds:
            self.start_execution_round(0, "initial")
        return rounds[-1]

    def record_subtask_execution(
        self,
        subtask: Any,
        evidence: Any,
        *,
        elapsed_ms: float,
        execution_detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "subtask_id": subtask.id,
            "question": subtask.question,
            "retrieval_mode": subtask.retrieval_mode,
            "planned_web_queries": list(subtask.web_queries or []),
            "is_refinement": bool(subtask.is_refinement),
            "started_at": _utc_now(),
            "elapsed_ms": round(elapsed_ms, 1),
            "success": evidence.success,
            "error": evidence.error,
            "summary": evidence.summary,
            "web_queries_used": list(evidence.web_queries_used or []),
            "sources": list(evidence.sources or []),
            "facts_extracted": list(evidence.facts_extracted or []),
            "formatted_context_chars": len(evidence.formatted_context or ""),
            "price_data": getattr(evidence, "price_data", None),
            "inferred_event_date": getattr(evidence, "inferred_event_date", None),
            "inferred_seller_ticker": getattr(evidence, "inferred_seller_ticker", None),
            "inferred_sold_ticker": getattr(evidence, "inferred_sold_ticker", None),
            "event_date_extraction": getattr(evidence, "event_date_extraction", None),
            "execution_detail": execution_detail or {},
        }
        self._current_round()["subtasks"].append(entry)

    def record_gap_analysis(
        self,
        round_index: int,
        *,
        sufficient: bool,
        gaps_summary: str,
        refinement_count: int,
        raw_response: Optional[Dict] = None,
        refinement_subtasks: Optional[List[Any]] = None,
    ) -> None:
        self._payload["execution"]["gap_analyses"].append({
            "round_index": round_index,
            "timestamp": _utc_now(),
            "sufficient": sufficient,
            "gaps_summary": gaps_summary,
            "refinement_subtasks_planned": refinement_count,
            "refinement_subtasks": [
                _subtask_to_dict(st) for st in (refinement_subtasks or [])
            ],
            "raw_response": raw_response,
        })

    def record_synthesis(
        self,
        *,
        gaps_summary: str,
        evidence_pack_chars: int,
        prompt_chars: int,
    ) -> None:
        self._payload["synthesis"] = {
            "gaps_summary": gaps_summary,
            "evidence_pack_chars": evidence_pack_chars,
            "prompt_chars": prompt_chars,
            "timestamp": _utc_now(),
        }

    def record_outcome(
        self,
        *,
        subtasks_executed: int,
        refinement_rounds: int,
        total_elapsed_ms: float,
        web_sources: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        self._payload["outcome"] = {
            "subtasks_executed": subtasks_executed,
            "refinement_rounds": refinement_rounds,
            "total_elapsed_ms": round(total_elapsed_ms, 1),
            "web_sources_count": len(web_sources),
            "web_sources": web_sources[:50],
            "error": error,
            "metadata": _sanitize_metadata(metadata) if metadata else {},
            "completed_at": _utc_now(),
        }

    def attach_engine_log_lines(self, lines: List[str]) -> None:
        self._payload["engine_log_lines"] = list(lines)[-1500:]

    def to_dict(self) -> Dict[str, Any]:
        return deepcopy(self._payload)

    def save(self) -> Path:
        DEEP_RESEARCH_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        path = DEEP_RESEARCH_LOGS_DIR / f"{self.log_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._payload, f, indent=2, ensure_ascii=False, default=str)
        logger.info("[DEEP_RESEARCH] Wrote structured log to %s", path)
        return path


def append_engine_log_lines(log_path: str | Path, lines: List[str]) -> None:
    """Merge captured Python log lines into an existing dprsh JSON file."""
    path = Path(log_path)
    if not path.is_file() or not lines:
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        existing = data.get("engine_log_lines") or []
        data["engine_log_lines"] = (existing + list(lines))[-1500:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning("Could not append engine_log_lines to %s: %s", path, exc)


def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    skip = {"full_signal_tables", "signals_table"}
    out = {}
    for k, v in metadata.items():
        if k in skip:
            continue
        if hasattr(v, "to_dict"):
            try:
                out[k] = v.to_dict()
            except Exception:
                out[k] = str(v)
        else:
            try:
                json.dumps(v, default=str)
                out[k] = v
            except (TypeError, ValueError):
                out[k] = str(v)
    return out
