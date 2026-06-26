"""Shared Anthropic client helpers."""

from __future__ import annotations

import json
import os
from typing import Any

from src.macro_intelligence.config import load_config


def _model() -> str:
    cfg = load_config()
    return os.environ.get("MACRO_CLAUDE_MODEL", cfg.get("claude", {}).get("model", "claude-sonnet-4-20250514"))


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def call_claude(system: str, user: str, max_tokens: int = 400, temperature: float = 0.0) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=_model(),
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
