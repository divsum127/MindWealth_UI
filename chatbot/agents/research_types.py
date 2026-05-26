"""
Shared dataclasses for Deep Research agent mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

RetrievalMode = Literal["internal", "web", "hybrid", "price_data"]
TemporalScope = Literal["historical", "recent", "any"]

_INVALID_QUESTION_PLACEHOLDERS = frozenset(
    {"research subtask", "research sub-task", "subtask", ""}
)


def is_valid_subtask_question(question: str) -> bool:
    q = (question or "").strip().lower()
    return bool(q) and q not in _INVALID_QUESTION_PLACEHOLDERS and len(q) >= 12


@dataclass
class ResearchSubTask:
    id: str
    question: str
    retrieval_mode: RetrievalMode
    rationale: str
    success_criteria: str
    web_queries: List[str] = field(default_factory=list)
    internal_scope: Optional[Dict[str, Any]] = None
    depends_on: List[str] = field(default_factory=list)
    temporal_scope: TemporalScope = "any"
    is_refinement: bool = False
    precedent_name: Optional[str] = None
    seller_ticker: Optional[str] = None
    sold_ticker: Optional[str] = None
    event_date: Optional[str] = None
    price_offsets_months: List[int] = field(default_factory=lambda: [1, 3, 6])


@dataclass
class ResearchPlan:
    user_question: str
    summary: str
    subtasks: List[ResearchSubTask]
    reasoning: str = ""
    query_analysis: Optional[Dict[str, Any]] = None


@dataclass
class SubTaskEvidence:
    subtask_id: str
    question: str
    retrieval_mode: RetrievalMode
    success: bool
    summary: str = ""
    formatted_context: str = ""
    sources: List[str] = field(default_factory=list)
    error: Optional[str] = None
    web_queries_used: List[str] = field(default_factory=list)
    facts_extracted: List[str] = field(default_factory=list)
    price_data: Optional[Dict[str, Any]] = None
    inferred_event_date: Optional[str] = None
    inferred_seller_ticker: Optional[str] = None
    inferred_sold_ticker: Optional[str] = None
    event_date_extraction: Optional[Dict[str, Any]] = None


@dataclass
class EvidenceStore:
    """Accumulates evidence across subtasks and refinement rounds."""

    plan: ResearchPlan
    entries: List[SubTaskEvidence] = field(default_factory=list)
    rounds_completed: int = 0

    def add(self, evidence: SubTaskEvidence) -> None:
        self.entries.append(evidence)

    def get_entry(self, subtask_id: str) -> Optional[SubTaskEvidence]:
        for e in self.entries:
            if e.subtask_id == subtask_id:
                return e
        return None

    def all_sources(self) -> List[str]:
        seen: set = set()
        out: List[str] = []
        for e in self.entries:
            for url in e.sources:
                if url and url not in seen:
                    seen.add(url)
                    out.append(url)
        return out

    def format_for_gap_analysis(self, max_chars: int = 6000) -> str:
        parts: List[str] = []
        total = 0
        for e in self.entries:
            block = (
                f"### Subtask {e.subtask_id} ({e.retrieval_mode})\n"
                f"Question: {e.question}\n"
                f"Success: {e.success}\n"
                f"Summary: {e.summary}\n"
            )
            if e.inferred_event_date:
                block += f"Inferred event date: {e.inferred_event_date}\n"
            if e.inferred_seller_ticker:
                block += f"Inferred seller ticker: {e.inferred_seller_ticker}\n"
            if e.inferred_sold_ticker:
                block += f"Inferred sold ticker: {e.inferred_sold_ticker}\n"
            if e.event_date_extraction and e.event_date_extraction.get("seller_is_listed") is False:
                block += "Seller: unlisted (e.g. Crown) — measure sold stock only.\n"
            if e.price_data:
                block += f"Price data: {str(e.price_data)[:800]}\n"
            if e.facts_extracted:
                block += "Facts: " + "; ".join(e.facts_extracted[:8]) + "\n"
            if e.error:
                block += f"Error: {e.error}\n"
            if total + len(block) > max_chars:
                block = block[: max_chars - total] + "\n...(truncated)\n"
                parts.append(block)
                break
            parts.append(block)
            total += len(block)
        return "\n".join(parts)

    def format_for_synthesis(self, max_web_chars: int = 12000) -> str:
        sections: List[str] = []
        web_used = 0
        for e in self.entries:
            header = f"## Subtask {e.subtask_id}: {e.question}\nMode: {e.retrieval_mode} | Success: {e.success}\n"
            body = e.formatted_context or e.summary or "(no content)"
            if e.retrieval_mode in ("web", "hybrid") and web_used + len(body) > max_web_chars:
                remaining = max(0, max_web_chars - web_used)
                body = body[:remaining] + "\n...(truncated)\n" if remaining else "(truncated)"
            web_used += len(body) if e.retrieval_mode in ("web", "hybrid") else 0
            sections.append(header + body)
        return "\n\n".join(sections)
