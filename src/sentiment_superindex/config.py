"""Load SSI_CONFIG.yaml and resolve paths."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config_paths import SSI_CONFIG, SSI_DB, SSI_POSITIONING_JSON

# SSI_CONFIG.yaml `staleness:` is the ONLY source of these numbers.
#
# They used to be duplicated as Python literals here and merged YAML-over-Python, which meant
# the same figures lived in eighteen places (this file, the YAML, a hardcoded mirror in the
# Nuxt repo, four test files, the decay study, and several docs). The 2026-08-18 audit found
# replies quoting a set -- weekly 10 / daily 1 / monthly 25 / flat 0.8 -- that had never been
# what was running: Rohit's own instruction (sheet C46) asked for weekly 8 / daily 3 /
# monthly 30 with per-signal decay, and Test 21 shipped exactly that on 2026-08-07. Keeping a
# second copy in code is what let the two drift apart unnoticed.
#
# There is deliberately no fallback: a missing or malformed `staleness:` block raises rather
# than silently scoring against a stale default (see `staleness_policy`).

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


REQUIRED_CADENCES = ("weekly", "daily", "monthly")


@lru_cache(maxsize=1)
def staleness_policy() -> tuple[dict[str, int], float, dict[str, float]]:
    """Return (max_stale_days, default penalty, per-signal penalty overrides).

    Sourced entirely from ``SSI_CONFIG.yaml``. Raises if the block is missing or incomplete --
    these values change the SSI score, so falling back to a guess would be worse than failing.
    """
    block = load_config().get("staleness") or {}
    max_days_raw = block.get("max_stale_days") or {}
    missing = [c for c in REQUIRED_CADENCES if c not in max_days_raw]
    if missing:
        raise ValueError(
            f"SSI_CONFIG.yaml staleness.max_stale_days is missing {missing}. "
            "This block is the single source of truth for staleness; add it rather than "
            "relying on a code default."
        )
    if "weight_penalty" not in block:
        raise ValueError(
            "SSI_CONFIG.yaml staleness.weight_penalty is required (single source of truth)."
        )
    max_days = {k: int(v) for k, v in max_days_raw.items()}
    default_penalty = float(block["weight_penalty"])
    overrides = {
        k: float(v) for k, v in (block.get("weight_penalty_by_signal") or {}).items()
    }
    return max_days, default_penalty, overrides


DEFAULT_MIN_AVAILABLE_COUNT: dict[str, int] = {"layer1": 3, "layer2": 4, "layer3": 2}
DEFAULT_MIN_NOMINAL_WEIGHT_RETAINED: float = 0.60


def coverage_policy() -> tuple[dict[str, int], float]:
    """Return (min available inputs per layer, min fraction of nominal weight retained).

    Backs the layer coverage gate in ``engine.superindex``. See the ``coverage:`` block in
    ``SSI_CONFIG.yaml`` for why the gate exists and what it suppresses.
    """
    block = load_config().get("coverage", {})
    min_count = {
        **DEFAULT_MIN_AVAILABLE_COUNT,
        **{k: int(v) for k, v in (block.get("min_available_count") or {}).items()},
    }
    min_weight = float(
        block.get("min_nominal_weight_retained", DEFAULT_MIN_NOMINAL_WEIGHT_RETAINED)
    )
    return min_count, min_weight


def weight_penalty_for(series_key: str) -> float:
    """Carry-forward weight multiplier when stale_days > 0 (1.0 = no penalty)."""
    _, default_penalty, overrides = staleness_policy()
    return float(overrides.get(series_key, default_penalty))


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
