"""
Minimal HTTP client for MindWealth's own REST API, used from inside the chatbot.

Why HTTP and not a direct import: ``api/`` already imports ``chatbot/``, so
importing ``api.services`` from the engine would create a circular import. The
API is in-process on localhost, so the round-trip cost is small.

Contract: **every** failure returns ``None``. These calls run inside a chatbot
job worker thread where an unhandled exception would fail the whole answer, and
conviction context is an enrichment — never a hard requirement.
"""

import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"


def _default_base_url() -> str:
    """Base URL for our own API, honouring the port this process was started with."""
    explicit = os.getenv("MINDWEALTH_API_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    port = os.getenv("API_PORT", "8506").strip() or "8506"
    return f"http://127.0.0.1:{port}/api/v1"


class MindWealthAPIClient:
    """Read-only client for the local MindWealth API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 8.0,
    ):
        self.base_url = (base_url or _default_base_url()).rstrip("/")
        # Routers depend on ``optional_api_key``, which is an alias for
        # ``require_api_key`` — when API_KEY is set in the environment the header
        # is mandatory.
        self.api_key = api_key if api_key is not None else os.getenv("API_KEY", "").strip()
        self.timeout = timeout

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        GET a JSON endpoint. Returns the decoded body, or ``None`` on any
        failure (connection error, timeout, non-2xx, bad JSON).
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers[API_KEY_HEADER] = self.api_key
        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.warning(f"MindWealth API GET {path} failed: {exc}")
            return None
        if response.status_code != 200:
            logger.warning(
                f"MindWealth API GET {path} returned {response.status_code}: "
                f"{response.text[:200]}"
            )
            return None
        try:
            return response.json()
        except ValueError as exc:
            logger.warning(f"MindWealth API GET {path} returned non-JSON: {exc}")
            return None
