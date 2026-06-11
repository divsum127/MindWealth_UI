"""Atomic write positioning.json."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from src.sentiment_superindex.config import positioning_json_path


def write_positioning_json(payload: dict[str, Any], path: Path | None = None) -> Path:
    out = path or positioning_json_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        os.replace(tmp, out)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return out


def read_positioning_json(path: Path | None = None) -> dict[str, Any] | None:
    out = path or positioning_json_path()
    if not out.exists():
        return None
    try:
        return json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        return None
