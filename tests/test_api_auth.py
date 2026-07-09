"""Auth API tests."""

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
from api.services import auth_service as auth_svc


class TestAuthAPI(unittest.TestCase):
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
                "RATE_LIMIT_ENABLED": "false",
            },
            clear=False,
        )
        self.env_patch.start()
        import importlib

        import api.dependencies as deps
        import api.services.auth_service as reloaded_auth

        importlib.reload(reloaded_auth)
        importlib.reload(deps)
        reloaded_auth.bootstrap_admin("admin@test.com", "adminpass123", name="Admin")
        self.api_headers = {"X-API-Key": "test-api-key"}
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env_patch.stop()
        os.environ.pop("API_KEY", None)
        os.environ.pop("USERS_FILE", None)
        os.environ.pop("JWT_SECRET", None)
        import importlib
        import api.dependencies as deps

        importlib.reload(deps)
        self.tmp.cleanup()

    def _login(self, email: str = "admin@test.com", password: str = "adminpass123") -> str:
        r = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            headers=self.api_headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    def test_health_requires_api_key(self) -> None:
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 401)
        r2 = self.client.get("/api/v1/health", headers=self.api_headers)
        self.assertEqual(r2.status_code, 200)

    def test_login_and_me(self) -> None:
        token = self._login()
        r = self.client.get(
            "/api/v1/auth/me",
            headers={**self.api_headers, "Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["email"], "admin@test.com")
        self.assertEqual(body["role"], "admin")

    def test_admin_invite_and_accept(self) -> None:
        token = self._login()
        admin_headers = {**self.api_headers, "Authorization": f"Bearer {token}"}
        invite = self.client.post(
            "/api/v1/auth/admin/invite",
            json={"email": "user@test.com", "name": "User"},
            headers=admin_headers,
        )
        self.assertEqual(invite.status_code, 200, invite.text)
        invite_body = invite.json()
        self.assertIn("invite_url", invite_body)

        accept = self.client.post(
            "/api/v1/auth/accept-invite",
            json={"token": invite_body["invite_token"], "password": "userpass123"},
            headers=self.api_headers,
        )
        self.assertEqual(accept.status_code, 200, accept.text)
        self.assertEqual(accept.json()["email"], "user@test.com")

        user_token = accept.json()["access_token"]
        me = self.client.get(
            "/api/v1/auth/me",
            headers={**self.api_headers, "Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["role"], "user")

    def test_admin_list_users(self) -> None:
        token = self._login()
        r = self.client.get(
            "/api/v1/auth/admin/users",
            headers={**self.api_headers, "Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 200)
        emails = {row["email"] for row in r.json()}
        self.assertIn("admin@test.com", emails)

    def test_chatbot_requires_user_jwt(self) -> None:
        r = self.client.post(
            "/api/v1/chatbot/sessions",
            json={"title": "x"},
            headers=self.api_headers,
        )
        self.assertEqual(r.status_code, 401)

        token = self._login()
        r2 = self.client.post(
            "/api/v1/chatbot/sessions",
            json={"title": "Secure"},
            headers={**self.api_headers, "Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r2.status_code, 201, r2.text)


if __name__ == "__main__":
    unittest.main()
