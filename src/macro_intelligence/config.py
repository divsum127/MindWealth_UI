"""Load CONFIG.yaml and resolve paths."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config_paths import MACRO_INTEL_CONFIG, MACRO_INTEL_DB, MACRO_INTEL_JSON_PATH


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    path = MACRO_INTEL_CONFIG
    if not path.exists():
        raise FileNotFoundError(f"Macro intelligence config not found: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_path() -> Path:
    import os

    from src.config_paths import MACRO_INTEL_DATA_DIR

    return Path(os.getenv("MACRO_INTEL_DB", str(MACRO_INTEL_DATA_DIR / "runic.db")))


def json_output_path() -> Path:
    import os

    from src.config_paths import MACRO_INTEL_OUTPUT_DIR

    return Path(os.getenv("MACRO_INTEL_JSON_PATH", str(MACRO_INTEL_OUTPUT_DIR / "runic_output.json")))
