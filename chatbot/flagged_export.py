"""
Serialize and persist flagged user/assistant pairs to JSON for debugging.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .config import FLAGGED_PAIRS_DIR

logger = logging.getLogger(__name__)


def serialize_metadata_for_json(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert message metadata to JSON-serializable dict (mirrors HistoryManager.save_history).
    """
    if not metadata:
        return {}

    out = metadata.copy()

    if "full_signal_tables" in out and out["full_signal_tables"]:
        tables = out["full_signal_tables"]
        out["full_signal_tables"] = {
            signal_type: df.to_dict("records") if hasattr(df, "to_dict") else df
            for signal_type, df in tables.items()
        }

    for key, value in list(out.items()):
        if key == "full_signal_tables":
            continue
        if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
            try:
                out[key] = value.to_dict("records")
            except Exception:
                out[key] = str(value)

    return out


def truncate_signal_tables(
    metadata: Dict[str, Any], max_rows_per_table: int
) -> Dict[str, Any]:
    """Return a shallow copy of metadata with full_signal_tables row-limited per table."""
    if not metadata or "full_signal_tables" not in metadata:
        return metadata

    m = deepcopy(metadata)
    tables = m.get("full_signal_tables") or {}
    if not isinstance(tables, dict):
        return m

    new_tables: Dict[str, Any] = {}
    for signal_type, rows in tables.items():
        if isinstance(rows, list):
            new_tables[signal_type] = rows[:max_rows_per_table]
        elif hasattr(rows, "iloc"):
            try:
                import pandas as pd

                df = rows
                if len(df) > max_rows_per_table:
                    df = df.iloc[:max_rows_per_table].copy()
                new_tables[signal_type] = df.to_dict("records")
            except Exception:
                new_tables[signal_type] = str(rows)[:5000]
        else:
            new_tables[signal_type] = rows

    m["full_signal_tables"] = new_tables
    return m


def _message_payload(
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]],
    timestamp: Optional[str],
    serialize_meta: bool,
    truncate_tables: bool,
    max_rows_per_table: int,
) -> Dict[str, Any]:
    meta = metadata or {}
    if serialize_meta:
        meta = serialize_metadata_for_json(meta)
    if truncate_tables:
        meta = truncate_signal_tables(meta, max_rows_per_table)
    return {
        "role": role,
        "content": content or "",
        "metadata": meta,
        "timestamp": timestamp,
    }


def build_flagged_payload(
    *,
    session_id: str,
    notes: str,
    user_message: Dict[str, Any],
    assistant_message: Dict[str, Any],
    include_full_tables: bool,
    max_rows_sample: int,
) -> Dict[str, Any]:
    """Assemble the JSON object written for one flagged pair."""
    u_meta = user_message.get("metadata") or {}
    a_meta = assistant_message.get("metadata") or {}

    truncate = not include_full_tables
    user_payload = _message_payload(
        "user",
        user_message.get("content", ""),
        u_meta,
        user_message.get("timestamp"),
        True,
        truncate,
        max_rows_sample,
    )
    assistant_payload = _message_payload(
        "assistant",
        assistant_message.get("content", ""),
        a_meta,
        assistant_message.get("timestamp"),
        True,
        truncate,
        max_rows_sample,
    )

    a_pm = assistant_payload["metadata"]
    flow_trace: List[Any] = []
    if isinstance(a_pm, dict):
        flow_trace = a_pm.get("flow_trace") or []

    engine_lines = (assistant_message.get("metadata") or {}).get("engine_log_lines")
    if not isinstance(engine_lines, list):
        engine_lines = []

    return {
        "exported_at": datetime.now().isoformat(),
        "session_id": session_id,
        "notes": notes or "",
        "user": user_payload,
        "assistant": assistant_payload,
        "logs": {
            "flow_trace": flow_trace,
            "engine_log_lines": engine_lines,
        },
    }


def save_flagged_pair(
    *,
    session_id: str,
    notes: str,
    user_message: Dict[str, Any],
    assistant_message: Dict[str, Any],
    include_full_tables: bool = False,
    max_rows_sample: int = 50,
) -> Path:
    """
    Write one JSON file under FLAGGED_PAIRS_DIR.

    Returns the path written.
    """
    FLAGGED_PAIRS_DIR.mkdir(parents=True, exist_ok=True)

    payload = build_flagged_payload(
        session_id=session_id,
        notes=notes,
        user_message=user_message,
        assistant_message=assistant_message,
        include_full_tables=include_full_tables,
        max_rows_sample=max_rows_sample,
    )

    date_part = datetime.now().strftime("%Y%m%d")
    short_id = uuid4().hex[:8]
    filename = f"flag_{date_part}_{short_id}.json"
    path = FLAGGED_PAIRS_DIR / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info("Saved flagged pair to %s", path)
    return path
