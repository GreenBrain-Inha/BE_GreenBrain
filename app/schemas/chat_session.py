"""Chat session schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatSessionResponse(BaseModel):
    id: UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionResponse]
    next_cursor: Optional[str]


class ChatSessionUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
