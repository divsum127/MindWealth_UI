"""Load SSI_CONFIG.yaml and resolve paths."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config_paths import SSI_CONFIG, SSI_DB, SSI_POSITIONING_JSON


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
