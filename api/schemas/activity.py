"""User activity log schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ActivityCategory = Literal["navigation", "clicks"]


class ActivityEventIn(BaseModel):
    category: ActivityCategory
    action: str = Field(min_length=1, max_length=64)
    path: str = Field(default="", max_length=512)
    label: str = Field(default="", max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActivityEventBatch(BaseModel):
    events: list[ActivityEventIn] = Field(min_length=1, max_length=50)
