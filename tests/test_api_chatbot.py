"""API tests for Chatbot routes."""

from __future__ import annotations

import importlib
import os
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


def _setup_auth(tmp_root: Path) -> tuple[dict[str, str], TestClient, object]:
    users_file = tmp_root / "users.json"
    env = {
        "USERS_FILE": str(users_file),
        "API_KEY": "test-api-key",
        "JWT_SECRET": "test-jwt-secret",
        "CHATBOT_REQUIRE_USER": "true",
        "RATE_LIMIT_ENABLED": "false",
    }
    env_patch = patch.dict(os.environ, env, clear=False)
    env_patch.start()
    import api.dependencies as deps
    import api.services.auth_service as auth_svc

    importlib.reload(auth_svc)
    importlib.reload(deps)
    auth_svc.bootstrap_admin("tester@test.com", "testpass123", name="Tester")
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "tester@test.com", "password": "testpass123"},
        headers={"X-API-Key": "test-api-key"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"X-API-Key": "test-api-key", "Authorization": f"Bearer {token}"}
    return headers, client, env_patch


class TestChatbotSessionsAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.history_dir = root / "history"
        self.jobs_dir = root / "jobs"
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
        self.headers, self.client, self.env_patch = _setup_auth(root)

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()
        self.env_patch.stop()
        os.environ.pop("API_KEY", None)
        os.environ.pop("USERS_FILE", None)
        importlib.reload(importlib.import_module("api.dependencies"))
        self.tmp.cleanup()

    def test_create_and_get_session(self) -> None:
        r = self.client.post("/api/v1/chatbot/sessions", json={"title": "Test"}, headers=self.headers)
        self.assertEqual(r.status_code, 201)
        session_id = r.json()["session_id"]
        r2 = self.client.get(f"/api/v1/chatbot/sessions/{session_id}", headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["title"], "Test")

    def test_list_sessions(self) -> None:
        self.client.post("/api/v1/chatbot/sessions", json={}, headers=self.headers)
        r = self.client.get("/api/v1/chatbot/sessions", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 1)

    def test_delete_session(self) -> None:
        session_id = self.client.post("/api/v1/chatbot/sessions", json={}, headers=self.headers).json()["session_id"]
        r = self.client.delete(f"/api/v1/chatbot/sessions/{session_id}", headers=self.headers)
        self.assertEqual(r.status_code, 204)


class TestChatbotAsyncJobs(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.history_dir = root / "history"
        self.jobs_dir = root / "jobs"
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
        self.headers, self.client, self.env_patch = _setup_auth(root)

    def tearDown(self) -> None:
        self.engine_patch.stop()
        for p in reversed(self.patches):
            p.stop()
        self.env_patch.stop()
        os.environ.pop("API_KEY", None)
        os.environ.pop("USERS_FILE", None)
        importlib.reload(importlib.import_module("api.dependencies"))
        self.tmp.cleanup()

    def test_enqueue_and_poll_job(self) -> None:
        session_id = self.client.post("/api/v1/chatbot/sessions", json={}, headers=self.headers).json()["session_id"]
        r = self.client.post(
            f"/api/v1/chatbot/sessions/{session_id}/messages",
            json={"message": "What are top signals?", "preset": "freeform"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 202)
        body = r.json()
        self.assertEqual(body["status"], "queued")
        job_id = body["job_id"]

        deadline = time.time() + 10
        status = "queued"
        while time.time() < deadline and status not in ("completed", "failed"):
            job = self.client.get(f"/api/v1/chatbot/jobs/{job_id}", headers=self.headers).json()
            status = job["status"]
            if status == "completed":
                self.assertEqual(job["result"]["content"], "Hello from mock")
                return
            time.sleep(0.2)
        self.fail(f"Job did not complete in time; last status={status}")

    def test_analyze_asset_requires_asset(self) -> None:
        r = self.client.post("/api/v1/chatbot/analyze-asset", json={}, headers=self.headers)
        self.assertEqual(r.status_code, 422)


class TestChatbotUtilitiesAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.headers, self.client, self.env_patch = _setup_auth(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.env_patch.stop()
        os.environ.pop("API_KEY", None)
        os.environ.pop("USERS_FILE", None)
        importlib.reload(importlib.import_module("api.dependencies"))
        self.tmp.cleanup()

    def test_config(self) -> None:
        r = self.client.get("/api/v1/chatbot/config", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("features", body)
        self.assertIn("models", body)

    def test_signal_types(self) -> None:
        r = self.client.get("/api/v1/chatbot/signal-types", headers=self.headers)
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


class TestHistorySerialization(unittest.TestCase):
    """
    Regression guard for the 500 on ``GET /chatbot/sessions/{id}/history``.

    ``HistoryManager.load_history`` rebuilds ``full_signal_tables`` into pandas
    DataFrames, and ``get_history`` used to hand those straight to the response
    serializer: ``PydanticSerializationError: Unable to serialize unknown type:
    <class 'pandas.core.frame.DataFrame'>``. The chat panel reads as dead when
    that happens, so the sanitizer must survive frames, numpy scalars, NaT and
    NaN.
    """

    def test_get_history_sanitizes_dataframes(self) -> None:
        import json

        import numpy as np
        import pandas as pd

        from api.services import chatbot_service as svc

        frame = pd.DataFrame(
            {
                "symbol": ["FPH.NZ", "MFT.NZ"],
                "score": [np.float64(31.8), np.nan],
                "rank": [np.int64(1), np.int64(2)],
                "signal_date": [pd.Timestamp("2026-08-14"), pd.NaT],
            }
        )
        messages = [
            {"role": "user", "content": "what should i buy", "metadata": {"display_prompt": "what should i buy"}},
            {
                "role": "assistant",
                "content": "answer",
                "metadata": {"full_signal_tables": {"entry": frame}, "rows_fetched": np.int64(2)},
            },
        ]

        engine = MagicMock()
        engine.get_conversation_history.return_value = messages

        with patch.object(svc, "ensure_session_exists", return_value=None), patch.object(
            svc, "ChatbotEngine", return_value=engine
        ):
            for display in (True, False):
                out = svc.get_history("session-1", display=display)
                json.dumps(out)  # raises TypeError if anything survived unsanitized

        with patch.object(svc, "ensure_session_exists", return_value=None), patch.object(
            svc, "ChatbotEngine", return_value=engine
        ):
            out = svc.get_history("session-1", display=True)

        rows = out[1]["metadata"]["full_signal_tables"]["entry"]
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "FPH.NZ")
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["signal_date"][:10], "2026-08-14")
        self.assertIsNone(rows[1]["score"], "NaN must become null, not the string 'nan'")
        self.assertIsNone(rows[1]["signal_date"], "NaT must become null")
        # The engine's own copy must keep the DataFrame — it is used in later turns.
        self.assertIsInstance(messages[1]["metadata"]["full_signal_tables"]["entry"], pd.DataFrame)


class TestOrphanedJobReconciliation(unittest.TestCase):
    """
    Jobs run in worker threads in the API process. A restart kills the thread
    but used to leave the record saying `running` forever, so a polling client
    never received an answer or an error — it spun until its own budget expired
    and reported the analyst as unreachable.
    """

    def test_running_jobs_are_failed_on_startup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp))
            queued = store.create(session_id="s1", request={"message": "a"})
            running = store.create(session_id="s1", request={"message": "b"})
            store.update(running["job_id"], status="running")
            done = store.create(session_id="s1", request={"message": "c"})
            store.update(done["job_id"], status="completed", result={"content": "answer"})

            self.assertEqual(store.fail_orphaned(), 2)

            for job_id in (queued["job_id"], running["job_id"]):
                rec = store.get(job_id)
                assert rec is not None
                self.assertEqual(rec["status"], "failed")
                self.assertIn("restarted", rec["error"])
                self.assertIsNotNone(rec["completed_at"])

            finished = store.get(done["job_id"])
            assert finished is not None
            self.assertEqual(finished["status"], "completed", "completed jobs must not be touched")
            self.assertEqual(finished["result"], {"content": "answer"})

    def test_second_call_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp))
            store.create(session_id="s1", request={"message": "a"})
            self.assertEqual(store.fail_orphaned(), 1)
            self.assertEqual(store.fail_orphaned(), 0)
