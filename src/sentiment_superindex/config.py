"""Load SSI_CONFIG.yaml and resolve paths."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config_paths import SSI_CONFIG, SSI_DB, SSI_POSITIONING_JSON

# Rohit staleness spec (A4) — overridden by SSI_CONFIG.yaml `staleness` block when present.
MAX_STALE_DAYS: dict[str, int] = {"weekly": 5, "daily": 1, "monthly": 25}
STALE_WEIGHT_PENALTY: float = 0.8

# Publication cadence per SSI input (DATA_SOURCES.yaml). Used for staleness caps + penalties.
SSI_INPUT_CADENCE: dict[str, str] = {
    "aaii_spread": "weekly",
    "naaim_exposure": "weekly",
    "put_call_ema": "daily",
    "cnn_fg": "daily",
    "mcclellan": "daily",
    "nh_nl_ratio": "daily",
    "hyg_lqd": "daily",
    "skew": "daily",
    "vix_ratio": "daily",
    "pct_above_200dma": "daily",
    "dbmf_beta": "daily",
    "cftc_fm_net": "weekly",
    "cftc_rm_net": "weekly",
    "gross_net": "weekly",
    "margin_debt": "monthly",
}


def staleness_policy() -> tuple[dict[str, int], float]:
    """Return (max_stale_days by cadence, stale weight penalty) from YAML + defaults."""
    block = load_config().get("staleness", {})
    max_days = {**MAX_STALE_DAYS, **(block.get("max_stale_days") or {})}
    penalty = float(block.get("weight_penalty", STALE_WEIGHT_PENALTY))
    return max_days, penalty


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    if not SSI_CONFIG.exists():
        raise FileNotFoundError(f"SSI config not found: {SSI_CONFIG}")
    with SSI_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_path() -> Path:
    import os

    from src.config_paths import SSI_DATA_DIR

    return Path(os.getenv("SSI_DB", str(SSI_DATA_DIR / "ssi.db")))


def positioning_json_path() -> Path:
    import os

    from src.config_paths import MACRO_INTEL_OUTPUT_DIR

    return Path(os.getenv("SSI_POSITIONING_JSON", str(MACRO_INTEL_OUTPUT_DIR / "positioning.json")))
