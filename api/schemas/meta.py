"""Schemas for GET /api/v1/meta."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DataUpdatedAt(BaseModel):
    date: str
    time: str
    datetime: str
    timezone: str


class MetaResponse(BaseModel):
    data_updated_at: DataUpdatedAt | None = None
    market_label: str | None = None
    source_files: dict[str, str] | None = None
