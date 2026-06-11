"""Regime: Python for 4 labels; Claude+Tavily for geo_overlay only."""

from __future__ import annotations

import json
from typing import Any

from src.macro_intelligence.claude._client import call_claude, parse_json_text
from src.macro_intelligence.claude.geo_news import fetch_geo_headlines
from src.macro_intelligence.config import load_config
from src.macro_intelligence.db.regime_log import upsert_macro_regime_log
from src.macro_intelligence.engine.regime_rules import build_python_regime
from src.macro_intelligence.models import RegimeState

GEO_SYSTEM = "Return ONLY JSON: {\"geo_overlay\": \"NEUTRAL|TRADE_WAR|SANCTIONS|REGIONAL_WAR|PANDEMIC|FINANCIAL_CRISIS\"}"


def classify_regime(
    date: str,
    context: dict[str, Any] | None = None,
    use_claude: bool = True,
    readings: dict[str, dict[str, Any]] | None = None,
) -> RegimeState:
    if not use_claude or not _has_api_key():
        regime = _heuristic_regime(date, context or {})
        payload = regime.to_dict()
        _log_regime(date, payload, combo_id=(context or {}).get("combo_id"))
        return regime

    base = build_python_regime(date, readings)
    geo = _classify_geo(date, use_claude=True)
    regime = RegimeState(
        fed_cycle=base.get("fed_cycle", "PAUSING"),
        curve_regime=base.get("curve_regime", "NORMAL"),
        geo_overlay=geo,
        val_regime=_map_val(base.get("val_regime", "NORMAL")),
        liquidity=base.get("liquidity", "GLOBAL_EASY"),
    )
    payload = {**regime.to_dict(), **{k: v for k, v in base.items() if k.endswith("_source")}}
    _log_regime(date, payload, combo_id=(context or {}).get("combo_id"))
    return regime


def _map_val(val: str) -> str:
    if "EXTREME" in val:
        return "EXTREME"
    if "ELEVATED" in val:
        return "ELEVATED"
    if "CHEAP" in val:
        return "CHEAP"
    return "FAIR"


def _classify_geo(date: str, use_claude: bool = True) -> str:
    if not use_claude or not _has_api_key():
        return _heuristic_geo(date)
    headlines = fetch_geo_headlines(date)
    user = f"Date: {date}. News context:\n{headlines or 'No headlines available.'}\nClassify geo_overlay."
    try:
        text = call_claude(GEO_SYSTEM, user, max_tokens=80)
        data = parse_json_text(text)
        return data.get("geo_overlay", "NEUTRAL")
    except Exception:
        return _heuristic_geo(date)


def _heuristic_regime(date: str, context: dict[str, Any]) -> RegimeState:
    from src.macro_intelligence.engine.fed_cycle import fed_cycle_at_date

    fixture_dims = {
        "2022-10-13": ("INVERTED", "SANCTIONS", "ELEVATED", "GLOBAL_TIGHT"),
        "2020-03-23": ("NORMAL", "PANDEMIC", "ELEVATED", "GLOBAL_EASY"),
        "2020-06-08": ("NORMAL", "PANDEMIC", "ELEVATED", "GLOBAL_EASY"),
        "2020-06-29": ("NORMAL", "PANDEMIC", "ELEVATED", "GLOBAL_EASY"),
        "2015-12-16": ("NORMAL", "NEUTRAL", "ELEVATED", "GLOBAL_EASY"),
        "2024-09-18": ("STEEPENING", "NEUTRAL", "EXTREME", "GLOBAL_EASY"),
    }
    fed, _ = fed_cycle_at_date(date)
    if date in fixture_dims:
        curve, geo, val, liq = fixture_dims[date]
        return RegimeState(fed, curve, geo, val, liq)
    base = build_python_regime(date)
    liq_map = {"GLOBAL_EASY": "GLOBAL_EASY", "GLOBAL_TIGHT": "GLOBAL_TIGHT", "NEUTRAL": "GLOBAL_EASY"}
    return RegimeState(
        fed_cycle=fed,
        curve_regime=base.get("curve_regime", "NORMAL"),
        geo_overlay=_heuristic_geo(date),
        val_regime=_map_val(base.get("val_regime", "NORMAL")),
        liquidity=liq_map.get(base.get("liquidity", "NEUTRAL"), "GLOBAL_EASY"),
    )


def _heuristic_geo(date: str) -> str:
    known = {
        "2022-10-13": "SANCTIONS",
        "2020-03-23": "PANDEMIC",
        "2020-06-08": "PANDEMIC",
        "2020-06-29": "PANDEMIC",
    }
    return known.get(date, "NEUTRAL")


def _has_api_key() -> bool:
    import os

    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _log_regime(date: str, regime: dict[str, Any], combo_id: int | None = None) -> None:
    upsert_macro_regime_log(date, regime, model="python+claude_geo", combo_id=combo_id)
