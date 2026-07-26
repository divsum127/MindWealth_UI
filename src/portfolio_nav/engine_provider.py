"""Adapter for Ahil's nav_engine.py — loaded when the module is present on disk.

Expected drop-in (when Ahil delivers nav_engine.py):

1. Copy/rename to: ``src/portfolio_nav/ahil_nav_engine.py``
   OR set env ``PORTFOLIO_NAV_ENGINE_MODULE`` to your module path.

2. Implement::

       def get_nav_history(
           book: str,
           *,
           forward_testing_root: Path | None = None,
           starting_nav: float = 10_000_000,
           n_slots: int = 60,
       ) -> dict[str, Any]:
           ...

   Return dict compatible with :class:`NavHistoryBundle` fields (mtm, closed, benchmark,
   monthly_returns, attribution) OR a NavHistoryBundle instance.

3. Restart API — workbook provider is bypassed automatically when engine loads.
"""

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from src.config_paths import BASE_DIR, MINDWEALTH_ROOT
from src.portfolio_nav.types import (
    AttributionRow,
    MonthlyReturn,
    NavHistoryBundle,
    NavPoint,
)

logger = logging.getLogger(__name__)


def _engine_config() -> dict[str, Any]:
    path = BASE_DIR / "config" / "portfolio_nav.yaml"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return cfg.get("engine") or {}


def _forward_testing_root() -> Path:
    cfg = _engine_config()
    custom = cfg.get("forward_testing_root")
    if custom:
        return Path(custom)
    return MINDWEALTH_ROOT / "trade_store" / "US" / "forward_testing"


def engine_available() -> bool:
    """True when get_nav_history is importable (engine may still fall back at runtime)."""
    module_name = os.getenv(
        "PORTFOLIO_NAV_ENGINE_MODULE",
        _engine_config().get("module") or "src.portfolio_nav.ahil_nav_engine",
    )
    try:
        mod = importlib.import_module(module_name)
        return callable(getattr(mod, "get_nav_history", None))
    except ImportError:
        return False


def _coerce_nav_point(raw: dict[str, Any]) -> NavPoint:
    return NavPoint(
        date=str(raw["date"]),
        value=float(raw["value"]),
        drawdown_pct=float(raw.get("drawdown_pct") or 0),
        high_water_mark=float(raw.get("high_water_mark") or raw["value"]),
    )


def _bundle_from_dict(book: str, payload: dict[str, Any]) -> NavHistoryBundle:
    def pts(key: str) -> list[NavPoint]:
        return [_coerce_nav_point(p) for p in (payload.get(key) or [])]

    monthly = [
        MonthlyReturn(month=str(m["month"]), return_pct=float(m["return_pct"]))
        for m in (payload.get("monthly_returns") or [])
    ]
    attribution = [
        AttributionRow(
            id=str(a["id"]),
            label=str(a["label"]),
            return_pct=float(a["return_pct"]),
            description=str(a.get("description") or ""),
        )
        for a in (payload.get("attribution") or [])
    ]
    return NavHistoryBundle(
        book=book,
        source=str(payload.get("source") or "nav_engine"),
        inception_nav=float(payload.get("inception_nav") or 10_000_000),
        mtm=pts("mtm"),
        closed=pts("closed"),
        mtm_daily=pts("mtm_daily"),
        closed_daily=pts("closed_daily"),
        benchmark=pts("benchmark"),
        monthly_returns=monthly,
        attribution=attribution,
        position_limit=payload.get("position_limit"),
        nav_history_note=payload.get("nav_history_note"),
        metadata=dict(payload.get("metadata") or {}),
    )


def load_engine_history(book: str) -> NavHistoryBundle | None:
    """Call Ahil nav_engine when installed; return None if module missing."""
    cfg = _engine_config()
    module_name = os.getenv("PORTFOLIO_NAV_ENGINE_MODULE", cfg.get("module") or "src.portfolio_nav.ahil_nav_engine")
    callable_name = cfg.get("callable") or "get_nav_history"
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        return None

    fn = getattr(mod, callable_name, None)
    if not callable(fn):
        logger.warning("nav_engine module %s missing callable %s", module_name, callable_name)
        return None

    import yaml as _yaml  # noqa: F401 — ensure yaml available for config elsewhere

    nav_cfg_path = BASE_DIR / "config" / "portfolio_nav.yaml"
    nav_cfg: dict[str, Any] = {}
    if nav_cfg_path.is_file():
        with nav_cfg_path.open(encoding="utf-8") as fh:
            nav_cfg = _yaml.safe_load(fh) or {}

    result = fn(
        book,
        forward_testing_root=_forward_testing_root(),
        starting_nav=float(nav_cfg.get("research_notional_usd") or 10_000_000),
        n_slots=int(nav_cfg.get("position_limit_n") or 60),
    )
    if isinstance(result, NavHistoryBundle):
        return result
    if isinstance(result, dict):
        return _bundle_from_dict(book, result)
    raise TypeError(f"{module_name}.{callable_name} must return dict or NavHistoryBundle")
