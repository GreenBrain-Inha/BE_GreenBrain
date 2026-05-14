"""Challenge API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    title: str
    description: str
    difficulty: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime]


class CurrentChallengeResponse(BaseModel):
    challenge: Optional[ChallengeResponse]


class GenerateChallengeResponse(BaseModel):
    challenge: ChallengeResponse
    created: bool


class AcceptChallengeResponse(BaseModel):
    challenge: ChallengeResponse
