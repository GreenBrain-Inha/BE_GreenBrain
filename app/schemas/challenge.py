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


class ChallengePhotoResponse(BaseModel):
    id: UUID
    challenge_id: UUID
    file_url: str
    created_at: datetime


class ChallengePhotoUploadChallengeResponse(BaseModel):
    id: UUID
    status: str
    completed_at: datetime


class ChallengePhotoUploadRewardResponse(BaseModel):
    type: str
    reward_amount: float
    tokens_remaining: float


class ChallengePhotoUploadResponse(BaseModel):
    photo: ChallengePhotoResponse
    challenge: ChallengePhotoUploadChallengeResponse
    reward: ChallengePhotoUploadRewardResponse


class ChallengeFeedPhotoResponse(BaseModel):
    id: UUID
    challenge_id: UUID
    file_url: str
    created_at: datetime


class ChallengeFeedChallengeResponse(BaseModel):
    id: UUID
    title: str
    description: str
    category: str
    difficulty: int


class ChallengeFeedUserResponse(BaseModel):
    id: UUID
    nickname: Optional[str]
    profile_image_url: Optional[str]


class ChallengeFeedItemResponse(BaseModel):
    photo: ChallengeFeedPhotoResponse
    challenge: ChallengeFeedChallengeResponse
    user: ChallengeFeedUserResponse
    like_count: int


class ChallengeFeedResponse(BaseModel):
    items: list[ChallengeFeedItemResponse]
