"""API tests for Chatbot routes."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from api.jobs.store import JobStore


class TestChatbotSessionsAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.history_dir = Path(self.tmp.name) / "history"
        self.jobs_dir = Path(self.tmp.name) / "jobs"
        self.history_dir.mkdir(parents=True)
        self.jobs_dir.mkdir(parents=True)
        self.patches = [
            patch("chatbot.config.HISTORY_DIR", self.history_dir),
            patch("chatbot.session_manager.HISTORY_DIR", self.history_dir),
            patch("chatbot.history_manager.HISTORY_DIR", self.history_dir),
            patch("api.jobs.store.CHATBOT_JOBS_DIR", self.jobs_dir),
            patch("api.jobs.store._store", None),
        ]
        for p in self.patches:
            p.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_create_and_get_session(self) -> None:
        r = self.client.post("/api/v1/chatbot/sessions", json={"title": "Test"})
        self.assertEqual(r.status_code, 201)
        session_id = r.json()["session_id"]
        r2 = self.client.get(f"/api/v1/chatbot/sessions/{session_id}")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["title"], "Test")

    def test_list_sessions(self) -> None:
        self.client.post("/api/v1/chatbot/sessions", json={})
        r = self.client.get("/api/v1/chatbot/sessions")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 1)

    def test_delete_session(self) -> None:
        session_id = self.client.post("/api/v1/chatbot/sessions", json={}).json()["session_id"]
        r = self.client.delete(f"/api/v1/chatbot/sessions/{session_id}")
        self.assertEqual(r.status_code, 204)


class TestChatbotAsyncJobs(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.history_dir = Path(self.tmp.name) / "history"
        self.jobs_dir = Path(self.tmp.name) / "jobs"
        self.history_dir.mkdir(parents=True)
        self.jobs_dir.mkdir(parents=True)

        def fake_smart_followup(**kwargs):
            return ("Hello from mock", {"route": "INTERNAL", "input_type": "smart_followup"})

        self.patches = [
            patch("chatbot.config.HISTORY_DIR", self.history_dir),
            patch("chatbot.session_manager.HISTORY_DIR", self.history_dir),
            patch("chatbot.history_manager.HISTORY_DIR", self.history_dir),
            patch("api.jobs.store.CHATBOT_JOBS_DIR", self.jobs_dir),
            patch("api.jobs.store._store", None),
        ]
        for p in self.patches:
            p.start()
        self.engine_patch = patch("api.jobs.runner.ChatbotEngine")
        mock_engine_cls = self.engine_patch.start()
        mock_engine = MagicMock()
        mock_engine.smart_followup_query.side_effect = fake_smart_followup
        mock_engine_cls.return_value = mock_engine
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.engine_patch.stop()
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_enqueue_and_poll_job(self) -> None:
        session_id = self.client.post("/api/v1/chatbot/sessions", json={}).json()["session_id"]
        r = self.client.post(
            f"/api/v1/chatbot/sessions/{session_id}/messages",
            json={"message": "What are top signals?", "preset": "freeform"},
        )
        self.assertEqual(r.status_code, 202)
        body = r.json()
        self.assertEqual(body["status"], "queued")
        job_id = body["job_id"]

        deadline = time.time() + 10
        status = "queued"
        while time.time() < deadline and status not in ("completed", "failed"):
            job = self.client.get(f"/api/v1/chatbot/jobs/{job_id}").json()
            status = job["status"]
            if status == "completed":
                self.assertEqual(job["result"]["content"], "Hello from mock")
                return
            time.sleep(0.2)
        self.fail(f"Job did not complete in time; last status={status}")

    def test_analyze_asset_requires_asset(self) -> None:
        r = self.client.post("/api/v1/chatbot/analyze-asset", json={})
        self.assertEqual(r.status_code, 422)


class TestChatbotUtilitiesAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_config(self) -> None:
        r = self.client.get("/api/v1/chatbot/config")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("features", body)
        self.assertIn("models", body)

    def test_signal_types(self) -> None:
        r = self.client.get("/api/v1/chatbot/signal-types")
        self.assertEqual(r.status_code, 200)
        self.assertIn("entry", r.json()["allowed"])


class TestJobStore(unittest.TestCase):
    def test_create_and_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp))
            job = store.create(session_id="s1", request={"message": "hi"})
            store.update(job["job_id"], status="running")
            loaded = store.get(job["job_id"])
            assert loaded is not None
            self.assertEqual(loaded["status"], "running")
