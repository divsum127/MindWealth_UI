"""Pytest session setup — isolate tests from repo .env (API_KEY, rate limits)."""

from __future__ import annotations

import os

import pytest

# Set before any test module imports api.main (load_dotenv uses override=False).
os.environ["API_KEY"] = ""
os.environ["RATE_LIMIT_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def _isolate_api_test_environment() -> None:
    """Reset rate-limit counters each test; keep API_KEY empty unless a test overrides."""
    from tests.api_test_helpers import disable_rate_limits

    disable_rate_limits()
    yield
