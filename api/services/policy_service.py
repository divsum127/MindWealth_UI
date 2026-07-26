"""Single loader for config/portfolio_policy.yaml — the five open Rohit decisions.

Every backend engine (sizing_engine, eviction_engine, four_book_engine,
ahil_nav_engine_core) reads its N / notional / rebalance-mode / sleeve-table /
siblings-scope from here, never hardcoded, so flipping a Rohit decision is a
one-line config edit (see OPEN_QUESTIONS_FOR_ROHIT.md Asks 1-5).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config_paths import BASE_DIR

_POLICY_PATH = BASE_DIR / "config" / "portfolio_policy.yaml"


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes")


@lru_cache(maxsize=1)
def _load_raw(_mtime: float) -> dict[str, Any]:
    if not _POLICY_PATH.is_file():
        return {}
    with _POLICY_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _raw_policy() -> dict[str, Any]:
    mtime = _POLICY_PATH.stat().st_mtime if _POLICY_PATH.is_file() else 0.0
    return _load_raw(mtime)


def get_policy() -> dict[str, Any]:
    """Full parsed policy document, config-file values only (no env overrides)."""
    return _raw_policy()


def get_notional() -> tuple[int, str]:
    """(notional_usd, source) — mirrors portfolio_service.get_portfolio_notional() precedence.

    Priority: PORTFOLIO_NOTIONAL env > PORTFOLIO_USE_RESEARCH_NOTIONAL flag > policy default.
    """
    env_val = os.getenv("PORTFOLIO_NOTIONAL")
    if env_val:
        try:
            return int(float(env_val)), "env"
        except ValueError:
            pass
    policy = _raw_policy().get("notional", {})
    if _truthy(os.getenv("PORTFOLIO_USE_RESEARCH_NOTIONAL")):
        return int(policy.get("research_usd") or 10_000_000), "research"
    return int(policy.get("usd") or 100_000_000), "default"


def get_n_slots() -> tuple[int, str]:
    """(n, source). PORTFOLIO_N_SLOTS env overrides the policy default."""
    env_val = os.getenv("PORTFOLIO_N_SLOTS")
    if env_val:
        try:
            return int(float(env_val)), "env"
        except ValueError:
            pass
    n_cfg = _raw_policy().get("n_slots", {})
    return int(n_cfg.get("value") or 60), n_cfg.get("status", "interim")


def get_rebalance_mode() -> tuple[str, str]:
    """(mode, source) — 'hold_original' | 'legacy_rebalance'."""
    env_val = os.getenv("PORTFOLIO_REBALANCE_MODE")
    if env_val and env_val.strip().lower() in ("hold_original", "legacy_rebalance"):
        return env_val.strip().lower(), "env"
    rb_cfg = _raw_policy().get("rebalance_mode", {})
    return str(rb_cfg.get("value") or "hold_original"), rb_cfg.get("status", "interim")


def get_eviction_margin_m() -> tuple[float, str]:
    env_val = os.getenv("PORTFOLIO_EVICTION_MARGIN_M")
    if env_val:
        try:
            return float(env_val), "env"
        except ValueError:
            pass
    ev_cfg = _raw_policy().get("eviction", {})
    return float(ev_cfg.get("margin_m") or 0.0), ev_cfg.get("status", "interim")


def get_f5_freeze_at_n() -> bool:
    return bool(_raw_policy().get("eviction", {}).get("f5_freeze_at_n", False))


def get_sleeves() -> list[dict[str, Any]]:
    return list(_raw_policy().get("sleeves", {}).get("list", []))


def get_sleeve_scenario_scale(scenario: str) -> float:
    scales = _raw_policy().get("sleeves", {}).get("scenario_scale", {})
    return float(scales.get(scenario, 1.0))


def get_auto_scenario_thresholds() -> dict[str, float]:
    """Thresholds behind ``scenario=auto`` regime pick (D4) — see ``resolve_auto_scenario()``
    in ``api/services/portfolio_service.py``. Falls back to the original hardcoded values if
    the policy block is missing (older config file)."""
    cfg = _raw_policy().get("auto_scenario", {})
    return {
        "vix_pctile_stress": float(cfg.get("vix_pctile_stress", 70.0)),
        "hy_pct_stress": float(cfg.get("hy_pct_stress", 4.0)),
        "ssi_multiplier_stress_below": float(cfg.get("ssi_multiplier_stress_below", 0.9)),
        "vix_pctile_lowvol": float(cfg.get("vix_pctile_lowvol", 30.0)),
        "ssi_multiplier_lowvol_at_least": float(cfg.get("ssi_multiplier_lowvol_at_least", 1.0)),
    }


def get_auto_scenario_status() -> str:
    return str(_raw_policy().get("auto_scenario", {}).get("status") or "interim")


def get_conviction_earliest_reliable_date() -> str:
    return str(_raw_policy().get("conviction_history", {}).get("earliest_reliable_date") or "2026-05-15")


def get_siblings_scope() -> str:
    return str(_raw_policy().get("same_asset_siblings", {}).get("scope") or "all_rows")


def policy_meta() -> dict[str, Any]:
    """Status of every open decision, for API transparency (extends portfolio_notional_source())."""
    _, notional_source = get_notional()
    _, n_source = get_n_slots()
    _, rebalance_source = get_rebalance_mode()
    _, eviction_source = get_eviction_margin_m()
    sleeves_cfg = _raw_policy().get("sleeves", {})
    siblings_cfg = _raw_policy().get("same_asset_siblings", {})
    return {
        "notional": notional_source,
        "n_slots": n_source,
        "rebalance_mode": rebalance_source,
        "eviction_margin_m": eviction_source,
        "sleeves": sleeves_cfg.get("status", "interim"),
        "same_asset_siblings": siblings_cfg.get("status", "confirmed"),
        "auto_scenario_thresholds": get_auto_scenario_status(),
    }
