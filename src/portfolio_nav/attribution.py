"""Four-book attribution proxy rows (until nav_engine per-book replay)."""

from __future__ import annotations

from typing import Any

import yaml

from src.config_paths import BASE_DIR
from src.portfolio_nav.types import AttributionRow


def load_nav_config() -> dict[str, Any]:
    path = BASE_DIR / "config" / "portfolio_nav.yaml"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def attribution_for_book(book: str) -> list[AttributionRow]:
    cfg = load_nav_config()
    proxy = cfg.get("attribution_proxy_cagr_pct") or {}
    effects = cfg.get("attribution_effects_pp") or {}
    base = float(proxy.get("base", 0))
    rows = [
        AttributionRow(
            id="base",
            label="BASE",
            return_pct=base,
            description="Equal-weight base book",
        ),
    ]
    if book in ("ssi", "cv", "enhanced"):
        rows.append(AttributionRow(
            id="ssi",
            label="BASE + SSI",
            return_pct=float(proxy.get("ssi", base)),
            description=f"SSI overlay effect +{effects.get('ssi', 0)}pp",
        ))
    if book in ("cv", "enhanced"):
        rows.append(AttributionRow(
            id="cv",
            label="BASE + CONVICTION",
            return_pct=float(proxy.get("cv", base)),
            description=f"Conviction overlay +{effects.get('conviction', 0)}pp",
        ))
    if book == "enhanced":
        rows.append(AttributionRow(
            id="enhanced",
            label="ENHANCED",
            return_pct=float(proxy.get("enhanced", base)),
            description="Production settings (SSI + Conviction)",
        ))
    return rows
