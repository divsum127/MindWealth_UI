"""Claude nightly macro intelligence briefing."""

from __future__ import annotations

import json
from typing import Any

from src.macro_intelligence.claude._client import call_claude, parse_json_text
from src.macro_intelligence.config import load_config

SYSTEM = (
    "You are a senior macro strategist. Write with the structure and precision shown "
    "in the Runic nightly sample: (1) one sentence dominant signal statement with the "
    "reason it outweighs competing signals; (2) why it dominates, with specific variable "
    "levels and dates; (3) the two closest historical analogs with exact dates and forward "
    "returns; (4) one sentence action recommendation. 200–250 words. No hedging language."
)


def generate_nightly_briefing(payload: dict[str, Any], use_claude: bool = True) -> str:
    if not use_claude:
        return _template_briefing(payload)

    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _template_briefing(payload)

    cfg = load_config()
    max_tokens = cfg.get("claude", {}).get("narrative_max_tokens", 500)
    user = (
        f"Active combos: {json.dumps(payload.get('active_combos', []))}. "
        f"Regime: {json.dumps(payload.get('regime', {}))}. "
        f"Analog dates: {json.dumps(payload.get('analog_dates', []))}. "
        f"All 12 variable readings: {json.dumps(payload.get('variables', {}))}. "
        f"Dominant signal: {payload.get('dominant_signal')}. "
        f"Direction: {payload.get('brave_fearful')}."
    )
    try:
        return call_claude(SYSTEM, user, max_tokens=max_tokens)
    except Exception:
        return _template_briefing(payload)


def _template_briefing(payload: dict[str, Any]) -> str:
    dom = payload.get("dominant_signal", "N/A")
    reason = payload.get("dominant_reason", "")
    brave = payload.get("brave_fearful", "NEUTRAL")
    analogs = payload.get("analog_dates", [])
    analog_txt = ", ".join(analogs[:2]) if analogs else "historical analogs pending backfill"
    return (
        f"The dominant macro signal is Combo {dom}, which outweighs competing signals because {reason} "
        f"Closest historical analogs include {analog_txt}. "
        f"The system posture is {brave}. "
        f"Hold existing positions; do not add broad equity exposure until energy and inflation legs clear."
    )
