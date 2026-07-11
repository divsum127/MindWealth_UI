"""Shared helpers for API test isolation."""

from __future__ import annotations

import os

from api.rate_limit import reload_rules, reset_rate_limit_storage


def disable_rate_limits() -> None:
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    reset_rate_limit_storage()
    reload_rules()
