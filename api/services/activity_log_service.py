"""Per-user activity logs (navigation, clicks, chat) when admin enables tracking."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.services import auth_service as auth_svc

_ROOT = Path(__file__).resolve().parents[2]
_LOGS_ROOT = Path(os.getenv("ACTIVITY_LOGS_DIR", str(_ROOT / "activity_logs")))

_file_lock = threading.Lock()
_SLUG_RE = re.compile(r"[^a-z0-9._-]+")


def logs_root() -> Path:
    return _LOGS_ROOT


def email_log_slug(email: str) -> str:
    slug = email.strip().lower().replace("@", "_at_").replace(".", "_")
    return _SLUG_RE.sub("_", slug).strip("_") or "unknown_user"


def user_log_dir(email: str) -> Path:
    return _LOGS_ROOT / email_log_slug(email)


def is_activity_logging_enabled(email: str) -> bool:
    user = auth_svc.find_user(email)
    if user is None:
        return False
    return bool(user.get("activity_logging_enabled"))


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_user_dir(email: str) -> Path:
    root = user_log_dir(email)
    root.mkdir(parents=True, exist_ok=True)
    profile_path = root / "profile.json"
    if not profile_path.exists():
        profile_path.write_text(
            json.dumps(
                {
                    "email": email.strip().lower(),
                    "activity_logging_enabled": True,
                    "created_at": _utc_iso(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return root


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with _file_lock:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _category_file(email: str, category: str) -> Path:
    root = _ensure_user_dir(email)
    return root / f"{category}.jsonl"


def log_navigation(
    email: str,
    *,
    action: str,
    path: str = "",
    label: str = "",
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not is_activity_logging_enabled(email):
        return False
    _append_jsonl(
        _category_file(email, "navigation"),
        {
            "ts": _utc_iso(),
            "action": action,
            "path": path,
            "label": label,
            "metadata": metadata or {},
        },
    )
    return True


def log_click(
    email: str,
    *,
    action: str,
    path: str = "",
    label: str = "",
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not is_activity_logging_enabled(email):
        return False
    _append_jsonl(
        _category_file(email, "clicks"),
        {
            "ts": _utc_iso(),
            "action": action,
            "path": path,
            "label": label,
            "metadata": metadata or {},
        },
    )
    return True


def log_chat(
    email: str,
    *,
    action: str,
    session_id: str = "",
    message_preview: str = "",
    preset: str = "",
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not is_activity_logging_enabled(email):
        return False
    preview = message_preview.strip()
    if len(preview) > 500:
        preview = preview[:497] + "..."
    _append_jsonl(
        _category_file(email, "chat"),
        {
            "ts": _utc_iso(),
            "action": action,
            "session_id": session_id,
            "message_preview": preview,
            "preset": preset,
            "metadata": metadata or {},
        },
    )
    return True


def ingest_client_events(email: str, events: list[dict[str, Any]]) -> int:
    if not is_activity_logging_enabled(email):
        return 0
    written = 0
    for event in events:
        category = str(event.get("category", "")).strip().lower()
        action = str(event.get("action", "event")).strip()[:64]
        path = str(event.get("path", "")).strip()[:512]
        label = str(event.get("label", "")).strip()[:256]
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if category == "navigation":
            if log_navigation(email, action=action, path=path, label=label, metadata=metadata):
                written += 1
        elif category == "clicks":
            if log_click(email, action=action, path=path, label=label, metadata=metadata):
                written += 1
    return written
