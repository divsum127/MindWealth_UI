"""
ResearchSynthesizer — builds final Claude prompt from EvidenceStore.
"""

from __future__ import annotations

import json

from prompts.engine import RESEARCH_SYNTHESIS_SYSTEM, RESEARCH_SYNTHESIS_USER_TEMPLATE

from .research_types import EvidenceStore


class ResearchSynthesizer:
    def build_prompt(
        self,
        store: EvidenceStore,
        gaps_summary: str = "",
        max_web_chars: int = 12000,
    ) -> str:
        evidence_pack = store.format_for_synthesis(max_web_chars=max_web_chars)
        query_ctx = ""
        qa = getattr(store.plan, "query_analysis", None)
        if qa:
            query_ctx = (
                "\n\n=== QUERY INTENT (for synthesis) ===\n"
                + json.dumps(qa, indent=2)
                + "\n=== END QUERY INTENT ===\n"
            )
        user_block = RESEARCH_SYNTHESIS_USER_TEMPLATE.format(
            user_question=store.plan.user_question,
            plan_summary=store.plan.summary,
            evidence_pack=evidence_pack + query_ctx,
            gaps_summary=gaps_summary or "(none noted)",
        )
        return f"{RESEARCH_SYNTHESIS_SYSTEM}\n\n{user_block}"
