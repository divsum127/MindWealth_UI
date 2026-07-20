"""Optional Claude copy for AI Analyst alert messages (spec: copy only, does not trigger)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from src.config_paths import BASE_DIR

AlertKind = Literal["degradation", "runic"]
_CACHE_PATH = BASE_DIR / "overwatch_store" / "alert_copy_cache.json"
_MAX_TOKENS = 180


def _enabled() -> bool:
    if os.getenv("ANALYST_USE_CLAUDE_COPY", "false").strip().lower() not in {"1", "true", "yes"}:
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY"))


def _cache_key(kind: AlertKind, context: dict[str, Any]) -> str:
    raw = json.dumps({"kind": kind, "context": context}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_cache() -> dict[str, str]:
    if not _CACHE_PATH.exists():
        return {}
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def generate_alert_copy(kind: AlertKind, context: dict[str, Any], fallback_html: str) -> str:
    """Return Claude-polished HTML or fallback template when disabled/unavailable."""
    if not _enabled():
        return fallback_html

    key = _cache_key(kind, context)
    cache = _load_cache()
    if key in cache:
        return cache[key]

    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        )
        if kind == "degradation":
            prompt = (
                "Rewrite this degradation alert for a trading panel. "
                "Hard data only, no hype. Keep under 3 lines HTML with <br>. "
                f"Context: {json.dumps(context, default=str)}"
            )
        else:
            prompt = (
                "Rewrite this macro runic alert for a trading panel. "
                "Hard data only. Keep under 4 lines HTML with <br>. "
                f"Context: {json.dumps(context, default=str)}"
            )
        msg = client.messages.create(
            model=os.getenv("ANALYST_CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(block, "text", "") for block in msg.content).strip()
        if text:
            cache[key] = text
            _save_cache(cache)
            return text
    except Exception:
        pass
    return fallback_html
