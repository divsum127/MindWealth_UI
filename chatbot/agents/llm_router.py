"""
LLM Router — single OpenAI call that decides whether a user query needs:
  • MindWealth internal signal data (CSV / smart_query pipeline)
  • Web search (Tavily) for live or external information
  • Neither (purely conversational / definitional, history-only)

This replaces brittle keyword routing for the web vs internal split.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from prompts.engine import ROUTER_SYSTEM, ROUTER_USER_TEMPLATE

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM = ROUTER_SYSTEM
_ROUTER_USER_TEMPLATE = ROUTER_USER_TEMPLATE

# Aliases for prompt changelog registration
LLM_ROUTER_SYSTEM = ROUTER_SYSTEM

# Level/ladder query wording that should always resolve to internal MindWealth
# signal data — never web search — even if the LLM router mis-classifies it.
# This is the deterministic safety net behind ROUTER_SYSTEM rule 8 (see
# prompts/engine.py): entry/exit/target/stop/resistance/take-profit/pivot/
# F-Stack questions must never trigger a Tavily web search for generic
# technical-analysis content (e.g. death cross, blog resistance levels).
_INTERNAL_LEVEL_QUERY_RE = re.compile(
    r"\b(entry\s+level|exit\s+level|resistance|support\s+level|take\s*profit|"
    r"stop\s*loss|stop\s*level|targets?|pivot|f[- ]?stack|"
    r"recent\s+entry|recent\s+exit)\b",
    re.I,
)

# Wording that indicates a genuine need for live/web information even when a
# level-style term is also present (e.g. "compare my TSM entry with today's
# TSM news"). When present, the internal-only override below is skipped so
# real hybrid questions still get web search.
_WEB_ONLY_SIGNAL_RE = re.compile(
    r"\b(news|earnings|press\s+release|analyst\s+(rating|action)|macro|"
    r"\bfed\b|federal\s+reserve|today.s\s+(news|price)|breaking|announcement)\b",
    re.I,
)


# Recommendation / screening / replacement wording. These questions must always
# consult MindWealth's own ranked buy + exit lists, per-signal quality scores and
# conviction data — a web-only answer is wrong even when it reads well. This is
# the deterministic safety net behind ROUTER_SYSTEM rule 9.
#
# Unlike the level override above this does NOT suppress web search: the desired
# outcome is HYBRID (internal primary + web supplementary), not internal-only.
_RECOMMENDATION_QUERY_RE = re.compile(
    r"(what|which|any)\s+(other\s+|new\s+)?(stock|share|ticker|name|posi(tion|tions)|"
    r"signal|signals|posn|equity|equities|compan(y|ies))s?\b.{0,40}\b(buy|sell|add|pick|"
    r"enter|exit|hold|consider|replace|recommend)"
    r"|\b(what|which)\s+(should|shall|do|would|can|could)\s+(i|we|you)\b.{0,40}"
    r"\b(buy|sell|add|pick|enter|exit|replace|invest|allocate|rotate|swap|deploy)\b"
    r"|\breplace(ment)?s?\b"
    r"|\b(recommend|recommendation|recommendations)\b"
    r"|\b(swap|rotate)\s+(in|into|out|out\s+of)\b"
    r"|\b(new\s+buy|buy)\s+signals?\b"
    r"|\b(exit|sell)\s+signals?\b"
    r"|\bsignal\s+quality\s+score\b"
    r"|\b(candidates?|shortlist|screen(ing)?|alternatives?|substitutes?)\b"
    r"|\bworth\s+(buying|adding|holding|selling)\b"
    r"|\bshould\s+(i|we)\s+(buy|sell|add|exit|hold|replace)\b",
    re.I,
)


# MindWealth's own vocabulary. A question that names our data, our signal types
# or our functions can only be answered from inside the platform — the web has
# no idea what a "claude report" or a "TRENDPULSE signal" is.
#
# Observed failure this guards: "give me a short summary about claude report"
# routed CONVERSATIONAL and the model asked whether Claude was a stock ticker,
# while `claude_report` is a first-class signal type backed by a live file that
# is refreshed daily.
_PLATFORM_VOCAB_RE = re.compile(
    r"\b(claude\s+(\w+\s+)?(report|analysis|shortlist(ed)?( signals?)?)|"
    r"claude.s\s+(report|analysis|shortlist)|comprehensive\s+(analysis\s+)?report|"
    r"shortlist(ed)?\s+signals?)\b"
    r"|\bsignal\s+types?\b"
    r"|\b(which|what)\s+(functions?|strategies|models?|signals?)\b.{0,30}\b(exist|available|have|use|run)\b"
    r"|\b(fractal\s*track|trendpulse|deltadrift|sigmashell|pulsegauge|baselinedivergence|"
    r"band\s*matrix|altitude\s*alpha|f[- ]?stack\s*analyzer|breadth\s*sbi)\b"
    r"|\bportfolio\s+target\s+achieved\b"
    r"|\bmindwealth\b"
    r"|\b(our|your|the)\s+(model|system|engine|platform|data)\b"
    r"|\bwhat\s+(data|reports?|signals?)\s+(do\s+)?(you|we)\s+(have|hold|track|cover)\b",
    re.I,
)

# Macro / regime / sentiment / portfolio wording. MindWealth computes all of
# this nightly (Runic combos, SSI layers, sizing multiplier, portfolio risk),
# so a web answer is not merely thinner — it contradicts our own engine.
#
# Observed failure this guards: "what is the current macro regime and which
# combo is dominant?" routed WEB_RAG and answered "transitional with mixed
# signals" from news sources while Runic had Combo F dominant, week 20 of 26,
# TACTICAL EASY MONEY. The word "combo" is MindWealth-only vocabulary.
_MACRO_QUERY_RE = re.compile(
    r"\b(macro\s+(regime|backdrop|picture|view)|current\s+regime|regime\b)"
    r"|\bcombo\s*[a-g]?\b|\brunic\b"
    r"|\b(ssi|super\s*sentiment|sentiment\s+(index|layer|regime))\b"
    r"|\b(fear\s*(and|&|/)?\s*greed|naaim|aaii|put[- ]?call)\b"
    r"|\b(market\s+breadth|breadth)\b"
    r"|\b(vix|vxts|cape|nfci|walcl|liquidity\s+(regime|conditions))\b"
    r"|\b(fed\s+cycle|yield\s+curve|steepening|inversion)\b"
    r"|\b(position\s+sizing|sizing\s+multiplier|portfolio\s+(nav|risk|exposure|allocation)|"
    r"cluster\s+weight|drawdown)\b"
    r"|\bsystem\s+posture\b|\bdominant\s+signal\b",
    re.I,
)


def apply_platform_vocab_internal_override(
    user_message: str,
    internal: bool,
    web: bool,
    queries,
    reasoning: str,
):
    """
    Force internal data for questions phrased in MindWealth's own vocabulary.

    Like the recommendation override this only ever turns internal ON; web is
    left as the router set it, so "claude report summary" goes internal-only
    while "claude report vs today's news" still lands on HYBRID.
    """
    if internal:
        return internal, web, queries, reasoning
    if not _PLATFORM_VOCAB_RE.search(user_message or ""):
        return internal, web, queries, reasoning
    new_reasoning = (
        f"{reasoning.strip()} + override: question names MindWealth's own data/"
        "signal types/functions — internal data forced."
    ).strip()
    return True, web, queries, new_reasoning


def apply_macro_internal_override(
    user_message: str,
    internal: bool,
    web: bool,
    queries,
    reasoning: str,
):
    """
    Force internal data for macro / regime / sentiment / portfolio questions.

    Web stays on where the router asked for it, so the answer becomes HYBRID:
    our Runic regime and SSI as SOURCE A, market colour as SOURCE B. What this
    prevents is the pure-web answer that contradicts our own nightly output.
    """
    if internal:
        return internal, web, queries, reasoning
    if not _MACRO_QUERY_RE.search(user_message or ""):
        return internal, web, queries, reasoning
    new_reasoning = (
        f"{reasoning.strip()} + override: macro/regime/sentiment/portfolio query "
        "— internal MindWealth macro data forced (web kept as supplementary)."
    ).strip()
    return True, web, queries, new_reasoning


def apply_recommendation_internal_override(
    user_message: str,
    internal: bool,
    web: bool,
    queries: Optional[List[str]],
    reasoning: str,
) -> Tuple[bool, bool, Optional[List[str]], str]:
    """
    Deterministic safety net: force ``needs_internal_signal_data=True`` for
    recommendation / screening / replacement questions ("what should I buy to
    replace FPH and MFT", "what should we buy based on our signals", "give me a
    signal quality score").

    Web search is deliberately left untouched. With both flags set the
    MasterRouter picks HYBRID, so the SynthesisAgent presents MindWealth signals
    as SOURCE A (primary) and web results as SOURCE B (supplementary). Without
    this, a router miss lands on WEB_RAG, which answers purely from web text and
    never touches the signal pipeline at all.
    """
    if internal:
        return internal, web, queries, reasoning
    if not _RECOMMENDATION_QUERY_RE.search(user_message or ""):
        return internal, web, queries, reasoning

    new_reasoning = (
        f"{reasoning.strip()} + override: recommendation/screening query — "
        "internal signal data forced (web kept as supplementary)."
    ).strip()
    return True, web, queries, new_reasoning


def apply_internal_level_override(
    user_message: str,
    internal: bool,
    web: bool,
    queries: Optional[List[str]],
    reasoning: str,
) -> Tuple[bool, bool, Optional[List[str]], str]:
    """
    Deterministic safety net: force internal-only routing for entry/exit/target/
    stop/resistance/take-profit/pivot/F-Stack queries about MindWealth signals,
    even when the LLM router mis-classified the query as needing web search.

    Does not override when the query also contains clearly web-only wording
    (news, earnings, macro, press release, etc.) so genuine hybrid asks
    (e.g. "compare my TSM entry with today's TSM news") still run web search.
    """
    if not web:
        return internal, web, queries, reasoning
    um = user_message or ""
    if not _INTERNAL_LEVEL_QUERY_RE.search(um):
        return internal, web, queries, reasoning
    if _WEB_ONLY_SIGNAL_RE.search(um):
        return internal, web, queries, reasoning

    new_reasoning = (
        f"{reasoning.strip()} + override: internal-only level/ladder query "
        "(entry/exit/target/stop/resistance) — web search suppressed."
    ).strip()
    return True, False, None, new_reasoning


@dataclass
class LLMRouteOutput:
    conversational_only: bool
    needs_internal_signal_data: bool
    needs_web_search: bool
    search_queries: Optional[List[str]]
    reasoning: str
    raw_error: Optional[str] = None


class LLMRouter:
    """Routes queries via a single structured LLM call (gpt-4o-mini)."""

    def __init__(
        self,
        api_key: Optional[str],
        model: str = "gpt-4o-mini",
    ):
        self._model = model
        self._client = None
        if api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
                logger.info(f"LLMRouter: OpenAI client ready (model={model})")
            except Exception as exc:
                logger.error(f"LLMRouter: failed to init OpenAI: {exc}")

    @property
    def available(self) -> bool:
        return self._client is not None

    def route(
        self,
        user_message: str,
        history_messages: Optional[List[Dict]] = None,
    ) -> LLMRouteOutput:
        """
        Decide routing. On failure, returns safe defaults (internal data, no web).
        """
        if not self._client:
            return LLMRouteOutput(
                conversational_only=False,
                needs_internal_signal_data=True,
                needs_web_search=False,
                search_queries=None,
                reasoning="LLM router unavailable — defaulting to internal signal pipeline",
                raw_error="no OpenAI client",
            )

        history = self._format_history(history_messages or [])
        user_prompt = _ROUTER_USER_TEMPLATE.format(
            today=date.today().isoformat(),
            history=history or "(none)",
            query=user_message.strip(),
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _ROUTER_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=400,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
        except Exception as exc:
            logger.error(f"LLMRouter: routing call failed: {exc}")
            return LLMRouteOutput(
                conversational_only=False,
                needs_internal_signal_data=True,
                needs_web_search=False,
                search_queries=None,
                reasoning=f"Router error, default internal: {exc}",
                raw_error=str(exc),
            )

        conv = bool(data.get("conversational_only", False))
        internal = bool(data.get("needs_internal_signal_data", True))
        web = bool(data.get("needs_web_search", False))
        queries = data.get("search_queries")
        reasoning = str(data.get("reasoning", "")).strip()

        if isinstance(queries, list):
            queries = [str(q).strip() for q in queries if q][:3]
        else:
            queries = None

        um = user_message.strip()

        # Consistency fixes
        if conv:
            internal = False
            web = False
            queries = None
        if not conv and not internal and not web:
            internal = True
        if web and not queries:
            queries = [user_message[:200]]

        # Platform-vocabulary questions must never stay CONVERSATIONAL: the model
        # answers them from general knowledge and invents a taxonomy. Observed:
        # "What signal types exist?" produced a textbook LONG/SHORT answer, and
        # "summary about claude report" asked whether Claude was a ticker.
        if conv and _PLATFORM_VOCAB_RE.search(um):
            conv = False
            internal = True
            reasoning = (
                f"{reasoning.strip()} + override: names MindWealth's own data — "
                "demoted from conversational to internal."
            ).strip()

        if not conv:
            internal, web, queries, reasoning = apply_internal_level_override(
                um, internal, web, queries, reasoning
            )
            # Runs after the level override so an internal-only level query keeps
            # web suppressed; this one only ever turns internal ON.
            internal, web, queries, reasoning = apply_recommendation_internal_override(
                um, internal, web, queries, reasoning
            )
            # Both only ever turn internal ON, so they compose with the two
            # above without weakening the internal-only level route.
            internal, web, queries, reasoning = apply_platform_vocab_internal_override(
                um, internal, web, queries, reasoning
            )
            internal, web, queries, reasoning = apply_macro_internal_override(
                um, internal, web, queries, reasoning
            )

        logger.info(
            f"[LLM_ROUTER] conv={conv} internal={internal} web={web} | {reasoning[:120]}"
        )

        return LLMRouteOutput(
            conversational_only=conv,
            needs_internal_signal_data=internal,
            needs_web_search=web,
            search_queries=queries,
            reasoning=reasoning,
        )

    @staticmethod
    def _format_history(messages: List[Dict], max_chars: int = 2000) -> str:
        parts = []
        total = 0
        for msg in messages[-8:]:
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = str(msg.get("content", ""))
            # Strip huge data blocks for the router prompt
            for marker in ("=== SIGNAL DATA", "=== COLUMN SELECTION", "=== ENTRY SIGNALS"):
                if marker in content:
                    content = content.split(marker)[0].strip()
                    break
            line = f"{role.upper()}: {content[:500]}"
            if total + len(line) > max_chars:
                break
            parts.append(line)
            total += len(line)
        return "\n".join(parts)
