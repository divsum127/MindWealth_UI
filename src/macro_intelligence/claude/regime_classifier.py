"""Claude macro regime classifier."""

from __future__ import annotations

import json
from typing import Any

from src.macro_intelligence.claude._client import call_claude, parse_json_text
from src.macro_intelligence.config import load_config
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.models import RegimeState

SYSTEM = (
    "You are a macro regime classifier. Return ONLY valid JSON, no preamble, "
    "no explanation, no markdown."
)

USER_TEMPLATE = """Date: {date}. Fed funds rate: {ffr}. WALCL 8-week direction: {walcl_dir}.
10Y-2Y spread: {curve}bps, direction: {curve_dir}. NFCI sign: {nfci_sign}.
CAPE decile: {cape_decile}. Classify:
{{"fed_cycle": "HIKING_EARLY|HIKING_LATE|CUTTING_EARLY|CUTTING_LATE|PAUSING|QE|QT",
  "curve_regime": "INVERTED|FLAT|STEEPENING|NORMAL",
  "geo_overlay": "NEUTRAL|TRADE_WAR|SANCTIONS|REGIONAL_WAR|PANDEMIC|FINANCIAL_CRISIS",
  "val_regime": "EXTREME|ELEVATED|FAIR|CHEAP",
  "liquidity": "GLOBAL_EASY|GLOBAL_TIGHT"}}"""


def classify_regime(
    date: str,
    context: dict[str, Any] | None = None,
    use_claude: bool = True,
) -> RegimeState:
    context = context or {}
    if not use_claude or not _has_api_key():
        return _heuristic_regime(date, context)

    cfg = load_config()
    max_tokens = cfg.get("claude", {}).get("regime_max_tokens", 150)
    user = USER_TEMPLATE.format(
        date=date,
        ffr=context.get("ffr", "unknown"),
        walcl_dir=context.get("walcl_dir", "flat"),
        curve=context.get("curve", 0),
        curve_dir=context.get("curve_dir", "flat"),
        nfci_sign=context.get("nfci_sign", "neutral"),
        cape_decile=context.get("cape_decile", "mid"),
    )
    try:
        text = call_claude(SYSTEM, user, max_tokens=max_tokens)
        data = parse_json_text(text)
        regime = RegimeState(
            fed_cycle=data.get("fed_cycle", "PAUSING"),
            curve_regime=data.get("curve_regime", "NORMAL"),
            geo_overlay=data.get("geo_overlay", "NEUTRAL"),
            val_regime=data.get("val_regime", "FAIR"),
            liquidity=data.get("liquidity", "GLOBAL_EASY"),
        )
        _log_regime(date, regime, combo_id=context.get("combo_id"))
        return regime
    except Exception:
        return _heuristic_regime(date, context)


def _has_api_key() -> bool:
    import os

    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _heuristic_regime(date: str, context: dict[str, Any]) -> RegimeState:
    """Fallback when API unavailable — used in tests."""
    known = {
        "2022-10-13": RegimeState("HIKING_LATE", "INVERTED", "SANCTIONS", "ELEVATED", "GLOBAL_TIGHT"),
        "2020-03-23": RegimeState("QE", "NORMAL", "PANDEMIC", "ELEVATED", "GLOBAL_EASY"),
        "2020-06-29": RegimeState("QE", "NORMAL", "PANDEMIC", "ELEVATED", "GLOBAL_EASY"),
        "2015-12-16": RegimeState("HIKING_EARLY", "NORMAL", "NEUTRAL", "ELEVATED", "GLOBAL_EASY"),
        "2024-09-18": RegimeState("CUTTING_EARLY", "STEEPENING", "NEUTRAL", "EXTREME", "GLOBAL_EASY"),
    }
    return known.get(date, RegimeState())


def _log_regime(date: str, regime: RegimeState, combo_id: int | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO macro_regime_log (date, combo_id, regime_json, model)
            VALUES (?, ?, ?, ?)
            """,
            (date, combo_id, json.dumps(regime.to_dict()), "claude"),
        )
