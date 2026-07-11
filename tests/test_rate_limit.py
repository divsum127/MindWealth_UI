"""Rate limiting tests."""

from __future__ import annotations

import importlib
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
from api.rate_limit import reload_rules, reset_rate_limit_storage


class TestRateLimitAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.users_file = Path(self.tmp.name) / "users.json"
        self.env_patch = patch.dict(
            os.environ,
            {
                "USERS_FILE": str(self.users_file),
                "API_KEY": "test-api-key",
                "JWT_SECRET": "test-jwt-secret",
                "CHATBOT_REQUIRE_USER": "true",
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_LOGIN_PER_MINUTE": "10/minute",
                "RATE_LIMIT_LOGIN_EMAIL_PER_MINUTE": "5/minute",
                "RATE_LIMIT_USER_CHAT_MESSAGES": "3/minute",
                "RATE_LIMIT_USER_READ": "30/10seconds;300/minute",
            },
            clear=False,
        )
        self.env_patch.start()
        reset_rate_limit_storage()
        reload_rules()
        import api.dependencies as deps
        import api.services.auth_service as auth_svc

        importlib.reload(auth_svc)
        importlib.reload(deps)
        auth_svc.bootstrap_admin("admin@test.com", "adminpass123", name="Admin")
        invite = auth_svc.admin_invite(email="user@test.com", name="User", role="user")
        auth_svc.accept_invite(invite["invite_token"], "userpass123")
        self.api_headers = {"X-API-Key": "test-api-key"}
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env_patch.stop()
        for key in (
            "API_KEY",
            "USERS_FILE",
            "JWT_SECRET",
            "RATE_LIMIT_ENABLED",
            "RATE_LIMIT_LOGIN_PER_MINUTE",
            "RATE_LIMIT_LOGIN_EMAIL_PER_MINUTE",
            "RATE_LIMIT_USER_CHAT_MESSAGES",
            "RATE_LIMIT_USER_READ",
        ):
            os.environ.pop(key, None)
        reset_rate_limit_storage()
        reload_rules()
        import importlib as il

        import api.dependencies as deps

        il.reload(deps)
        self.tmp.cleanup()

    def _login_token(self, email: str, password: str) -> str:
        r = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            headers=self.api_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    def test_login_burst_returns_429(self) -> None:
        codes: list[int] = []
        for _ in range(12):
            r = self.client.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.com", "password": "wrong"},
                headers=self.api_headers,
            )
            codes.append(r.status_code)
        self.assertIn(429, codes)
        idx = codes.index(429)
        self.assertEqual(idx, 5)
        self.assertEqual(r.json().get("detail"), "Rate limit exceeded")
        self.assertIn("Retry-After", r.headers)

    def test_user_chat_message_burst_returns_429(self) -> None:
        token = self._login_token("user@test.com", "userpass123")
        headers = {**self.api_headers, "Authorization": f"Bearer {token}"}
        session_id = self.client.post(
            "/api/v1/chatbot/sessions",
            json={"title": "RL"},
            headers=headers,
        ).json()["session_id"]

        with patch("api.services.chatbot_service.enqueue_message", return_value={"job_id": "j1", "status": "queued"}):
            codes = []
            for i in range(4):
                r = self.client.post(
                    f"/api/v1/chatbot/sessions/{session_id}/messages",
                    json={"message": f"msg {i}", "preset": "freeform"},
                    headers=headers,
                )
                codes.append(r.status_code)
        self.assertEqual(codes[:3], [202, 202, 202])
        self.assertEqual(codes[3], 429)

    def test_user_read_burst_under_limit_stays_200(self) -> None:
        token = self._login_token("user@test.com", "userpass123")
        headers = {**self.api_headers, "Authorization": f"Bearer {token}"}
        for _ in range(25):
            r = self.client.get("/api/v1/signals/reports", headers=headers)
            self.assertEqual(r.status_code, 200, r.text)

    def test_user_read_burst_over_limit_returns_429(self) -> None:
        token = self._login_token("user@test.com", "userpass123")
        headers = {**self.api_headers, "Authorization": f"Bearer {token}"}
        for _ in range(31):
            r = self.client.get("/api/v1/signals/reports", headers=headers)
            if r.status_code == 429:
                self.assertEqual(r.json().get("detail"), "Rate limit exceeded")
                return
        self.fail("Expected 429 after read burst")

    def test_admin_read_burst_higher_than_user(self) -> None:
        token = self._login_token("admin@test.com", "adminpass123")
        headers = {**self.api_headers, "Authorization": f"Bearer {token}"}
        for _ in range(50):
            r = self.client.get("/api/v1/signals/reports", headers=headers)
            self.assertEqual(r.status_code, 200, r.text)

    def test_rate_limit_disabled_skips_429(self) -> None:
        os.environ["RATE_LIMIT_ENABLED"] = "false"
        reset_rate_limit_storage()
        reload_rules()
        codes = []
        for _ in range(15):
            r = self.client.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.com", "password": "wrong"},
                headers=self.api_headers,
            )
            codes.append(r.status_code)
        self.assertNotIn(429, codes)


if __name__ == "__main__":
    unittest.main()
