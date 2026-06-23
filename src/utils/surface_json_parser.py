"""Parse <surface_json> blocks from Claude signals reports."""

from __future__ import annotations

import json
import re
from typing import Any

_SURFACE_JSON_RE = re.compile(r"<surface_json>\s*(\{.*?\})\s*</surface_json>", re.DOTALL)


def extract_surface_json_text(report_text: str) -> str | None:
    if not report_text:
        return None
    match = _SURFACE_JSON_RE.search(report_text)
    return match.group(1) if match else None


def parse_surface_json(report_text: str) -> list[dict[str, Any]]:
    """Return normalized surface_data rows from a Claude report."""
    raw = extract_surface_json_text(report_text)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = payload.get("surface_data", [])
    if not isinstance(rows, list):
        return []
    return [normalize_surface_row(row) for row in rows if isinstance(row, dict)]


def normalize_surface_row(row: dict[str, Any]) -> dict[str, Any]:
    """Unify legacy quality_score with composite_score and expected_return aliases."""
    out = dict(row)
    if out.get("composite_score") is None and out.get("quality_score") is not None:
        out["composite_score"] = out["quality_score"]
    if out.get("er") is None and out.get("expected_return") is not None:
        out["er"] = out["expected_return"]
    if out.get("yield_trap") is None and out.get("yield_trap_warning") is not None:
        out["yield_trap"] = out["yield_trap_warning"]
    return out
