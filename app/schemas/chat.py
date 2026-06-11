"""Chat message schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatModelListResponse(BaseModel):
    items: list[str]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model_id: Optional[str] = Field(default=None, min_length=1, max_length=160)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message must not be blank")
        return stripped

    @field_validator("model_id")
    @classmethod
    def normalize_model_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Model ID must not be blank")
        return stripped


class ChatResponse(BaseModel):
    message_id: UUID
    response_message_id: UUID
    response: str
    carbon_gco2eq: Optional[float]
    tokens_remaining: int
    tokens_deducted: int
    exhausted: bool
    session_title: Optional[str]
    model_id: str


class ChatMessageItem(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    carbon_gco2eq: Optional[float]
    model_id: Optional[str]
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageItem]
    next_cursor: Optional[str]
