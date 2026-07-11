"""Activity logging tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from api.services import activity_log_service as activity_svc
from api.services import auth_service as auth_svc


class TestActivityLog(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.users_file = Path(self.tmp.name) / "users.json"
        self.logs_dir = Path(self.tmp.name) / "activity_logs"
        self.env_patch = patch.dict(
            os.environ,
            {
                "USERS_FILE": str(self.users_file),
                "ACTIVITY_LOGS_DIR": str(self.logs_dir),
                "API_KEY": "test-api-key",
                "JWT_SECRET": "test-jwt-secret",
                "RATE_LIMIT_ENABLED": "false",
            },
            clear=False,
        )
        self.env_patch.start()
        import importlib

        import api.dependencies as deps
        import api.services.activity_log_service as reloaded_activity
        import api.services.auth_service as reloaded_auth

        importlib.reload(reloaded_auth)
        importlib.reload(reloaded_activity)
        importlib.reload(deps)
        auth_svc.bootstrap_admin("admin@test.com", "adminpass123", name="Admin")
        auth_svc.admin_invite(email="tracked@test.com", name="Tracked", role="user")
        users = auth_svc.load_users()
        for row in users:
            if row["email"] == "tracked@test.com":
                row["activity_logging_enabled"] = True
        auth_svc.save_users(users)
        self.api_headers = {"X-API-Key": "test-api-key"}
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env_patch.stop()
        os.environ.pop("API_KEY", None)
        os.environ.pop("USERS_FILE", None)
        os.environ.pop("JWT_SECRET", None)
        os.environ.pop("ACTIVITY_LOGS_DIR", None)
        import importlib
        import api.dependencies as deps

        importlib.reload(deps)
        self.tmp.cleanup()

    def _login(self, email: str, password: str) -> str:
        r = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            headers=self.api_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    def test_me_includes_logging_flag(self) -> None:
        token = self._login("admin@test.com", "adminpass123")
        r = self.client.get(
            "/api/v1/auth/me",
            headers={**self.api_headers, "Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("activity_logging_enabled", r.json())

    def test_ingest_writes_log_files(self) -> None:
        auth_svc.admin_patch_user("tracked@test.com", activity_logging_enabled=True)
        invite = auth_svc.admin_list_users()
        # accept invite for tracked user - they're invited, need password
        users = auth_svc.load_users()
        token = next(u["invite_token"] for u in users if u["email"] == "tracked@test.com")
        accept = self.client.post(
            "/api/v1/auth/accept-invite",
            json={"token": token, "password": "trackpass123"},
            headers=self.api_headers,
        )
        self.assertEqual(accept.status_code, 200, accept.text)
        user_token = accept.json()["access_token"]
        r = self.client.post(
            "/api/v1/activity/events",
            json={
                "events": [
                    {
                        "category": "navigation",
                        "action": "page_view",
                        "path": "/dashboard",
                        "metadata": {"from": "/login"},
                    },
                    {
                        "category": "clicks",
                        "action": "click",
                        "path": "/dashboard",
                        "label": "Signals",
                    },
                ]
            },
            headers={**self.api_headers, "Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["written"], 2)
        log_dir = activity_svc.user_log_dir("tracked@test.com")
        nav_lines = (log_dir / "navigation.jsonl").read_text(encoding="utf-8").strip().splitlines()
        click_lines = (log_dir / "clicks.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(nav_lines), 1)
        self.assertEqual(len(click_lines), 1)
        self.assertEqual(json.loads(nav_lines[0])["path"], "/dashboard")

    def test_skips_when_logging_disabled(self) -> None:
        token = self._login("admin@test.com", "adminpass123")
        r = self.client.post(
            "/api/v1/activity/events",
            json={"events": [{"category": "navigation", "action": "page_view", "path": "/"}]},
            headers={**self.api_headers, "Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["written"], 0)
        self.assertFalse((activity_svc.user_log_dir("admin@test.com") / "navigation.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
