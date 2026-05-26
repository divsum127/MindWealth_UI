"""
Gate for Deep Research mode — toggle, query_kind, and auto-detect heuristics.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

_DEEP_RESEARCH_KEYWORDS = [
    r"\bdeep research\b",
    r"\bcomprehensive research\b",
    r"\bthorough research\b",
    r"\binvestigate\b",
    r"\bprecedent\b",
    r"\bhistorical\b",
    r"\bwhat happened after\b",
    r"\b1\s*month\b.*\b3\s*month\b",
    r"\b3\s*months?\b.*\b6\s*months?\b",
    r"\bblock sale\b",
    r"\bblock trade\b",
    r"\bdivestment\b",
    r"\bselldown\b",
    r"\bplacement\b",
    r"\bcompare\b.*\b(precedent|history|past)\b",
]

_FRUSTRATION_PATTERNS = [
    r"\bwhy haven'?t you\b",
    r"\buseless\b",
    r"\bnot helpful\b",
    r"\byou should have\b",
    r"\bdo the research\b",
    r"\blook at sales\b",
]


def evaluate_deep_research_gate(
    user_message: str,
    history_messages: Optional[List[Dict]] = None,
    *,
    query_kind: Optional[str] = None,
    deep_research_enabled: bool = False,
    enable_deep_research_config: bool = True,
) -> tuple[bool, Dict]:
    """
    Return (use_deep_research, gate_info) for routing and structured logs.
    """
    info: Dict = {
        "enabled_config": enable_deep_research_config,
        "session_toggle": deep_research_enabled,
        "query_kind": query_kind,
        "auto_detect_score": 0,
        "trigger": None,
        "matched_keywords": [],
    }

    if not enable_deep_research_config:
        info["trigger"] = "disabled"
        return False, info
    if query_kind == "deep_research":
        info["trigger"] = "query_kind"
        return True, info
    if deep_research_enabled:
        info["trigger"] = "session_toggle"
        return True, info

    text = (user_message or "").strip().lower()
    if not text:
        info["trigger"] = "empty_query"
        return False, info

    score = 0
    matched = []
    for pat in _DEEP_RESEARCH_KEYWORDS:
        if re.search(pat, text, re.I):
            score += 1
            matched.append(pat)

    if len(re.findall(r"\b(trustpower|z energy|genesis|meridian|mercury|air new zealand|infratil|ift)\b", text, re.I)) >= 2:
        score += 2
        matched.append("multi_nz_precedent_entities")
    if re.search(r"\b(nzx|nzx announcements|research notes)\b", text, re.I):
        score += 1
        matched.append("nzx_sources")

    for pat in _FRUSTRATION_PATTERNS:
        if re.search(pat, text, re.I):
            score += 2
            matched.append(f"frustration:{pat}")
            break

    if history_messages:
        last_assistant = ""
        for msg in reversed(history_messages):
            if msg.get("role") == "assistant":
                last_assistant = str(msg.get("content", "")).lower()
                break
        if last_assistant and any(
            p in last_assistant
            for p in (
                "cannot provide specific",
                "do not contain",
                "web search results do not",
                "research plan",
                "you would need to research",
            )
        ):
            score += 2
            matched.append("prior_thin_web_answer")

    info["auto_detect_score"] = score
    info["matched_keywords"] = matched[:20]
    if score >= 2:
        info["trigger"] = "auto_detect"
        return True, info

    info["trigger"] = "below_threshold"
    return False, info


def should_deep_research(
    user_message: str,
    history_messages: Optional[List[Dict]] = None,
    *,
    query_kind: Optional[str] = None,
    deep_research_enabled: bool = False,
    enable_deep_research_config: bool = True,
) -> bool:
    """Return True if this query should use the DEEP_RESEARCH pipeline."""
    use, _ = evaluate_deep_research_gate(
        user_message,
        history_messages,
        query_kind=query_kind,
        deep_research_enabled=deep_research_enabled,
        enable_deep_research_config=enable_deep_research_config,
    )
    return use
