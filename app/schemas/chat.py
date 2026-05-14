"""Chat message schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message must not be blank")
        return stripped


class ChatResponse(BaseModel):
    message_id: UUID
    response_message_id: UUID
    response: str
    carbon_gco2eq: Optional[float]
    tokens_remaining: float
    exhausted: bool
    session_title: Optional[str]


class ChatMessageItem(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    carbon_gco2eq: Optional[float]
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageItem]
    next_cursor: Optional[str]
