"""Token API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TokenStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    tokens_remaining: float
    upload_reward_given: float
    like_reward_given: float
    total_reward_given: float
    challenge_count: int
    updated_at: datetime
