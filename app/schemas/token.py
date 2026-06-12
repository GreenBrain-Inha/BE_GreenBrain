"""Token API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TokenStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    tokens_remaining: int
    upload_reward_given: int
    like_reward_given: int
    total_reward_given: int
    challenge_count: int
    updated_at: datetime
