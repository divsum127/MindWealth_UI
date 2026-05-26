"""FastAPI dependencies."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Header, HTTPException, status

API_KEY = os.getenv("API_KEY", "").strip()
API_KEY_HEADER = "X-API-Key"


async def optional_api_key(
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Require X-API-Key when API_KEY env is set."""
    if not API_KEY:
        return
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
