"""File-based persistence for async chatbot jobs."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.config_paths import BASE_DIR

CHATBOT_JOBS_DIR = BASE_DIR / os.getenv("CHATBOT_JOBS_DIR", "chatbot/jobs")

JobStatus = str  # queued | running | completed | failed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else CHATBOT_JOBS_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def create(
        self,
        *,
        session_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        job_id = str(uuid4())
        record: dict[str, Any] = {
            "job_id": job_id,
            "session_id": session_id,
            "status": "queued",
            "created_at": _utc_now(),
            "started_at": None,
            "completed_at": None,
            "request": request,
            "flow_steps": [],
            "result": None,
            "error": None,
        }
        self._write(job_id, record)
        return record

    def get(self, job_id: str) -> dict[str, Any] | None:
        path = self._path(job_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def update(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        record = self.get(job_id)
        if record is None:
            return None
        record.update(fields)
        self._write(job_id, record)
        return record

    def append_flow_step(self, job_id: str, stage: str, detail: str) -> None:
        record = self.get(job_id)
        if record is None:
            return
        steps = list(record.get("flow_steps") or [])
        steps.append({"stage": stage, "detail": detail, "timestamp": _utc_now()})
        record["flow_steps"] = steps
        self._write(job_id, record)

    def list_by_session(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("session_id") == session_id:
                jobs.append(data)
            if len(jobs) >= limit:
                break
        return jobs

    def fail_orphaned(self) -> int:
        """
        Mark jobs left ``queued``/``running`` by a previous process as failed.

        Jobs execute in worker threads inside this process. A restart (deploy,
        crash, ``systemctl restart``) kills the thread but leaves the on-disk
        record saying ``running`` forever, so a client polling that job never
        gets an answer and never gets an error either — it just spins until its
        own budget expires and shows "Could not reach the analyst".

        Called once at startup, before any new job can be created.
        """
        orphaned = 0
        for path in self.root.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if record.get("status") not in {"queued", "running"}:
                continue
            record["status"] = "failed"
            record["completed_at"] = _utc_now()
            record["error"] = "Interrupted — the API restarted while this answer was being generated."
            try:
                self._write(record["job_id"], record)
                orphaned += 1
            except (OSError, KeyError):
                continue
        return orphaned

    def _write(self, job_id: str, record: dict[str, Any]) -> None:
        path = self._path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".job_", suffix=".json", dir=path.parent)
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            tmp_path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise


_store: JobStore | None = None


def get_job_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
