"""
LLM Router — single OpenAI call that decides whether a user query needs:
  • MindWealth internal signal data (CSV / smart_query pipeline)
  • Web search (Tavily) for live or external information
  • Neither (purely conversational / definitional, history-only)

This replaces brittle keyword routing for the web vs internal split.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from prompts.engine import ROUTER_SYSTEM, ROUTER_USER_TEMPLATE

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM = ROUTER_SYSTEM
_ROUTER_USER_TEMPLATE = ROUTER_USER_TEMPLATE

# Aliases for prompt changelog registration
LLM_ROUTER_SYSTEM = ROUTER_SYSTEM


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
