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


class ChallengeFeedItemResponse(BaseModel):
    photo_id: UUID
    challenge_id: UUID
    user_id: UUID
    nickname: Optional[str]
    profile_image_url: Optional[str]
    title: str
    category: str
    photo_url: str
    like_count: int
    liked_by_me: bool
    carbon_saved_gco2eq: Optional[float]
    created_at: datetime


class ChallengeFeedResponse(BaseModel):
    items: list[ChallengeFeedItemResponse]
    total: int
    limit: int
    offset: int


class ChallengePhotoLikeResponse(BaseModel):
    photo_id: UUID
    liked: bool
    like_count: int
    reward_given: bool
    reward_amount: float
    tokens_remaining: Optional[float]


class ChallengePhotoLikedUserItem(BaseModel):
    user_id: UUID
    nickname: Optional[str]
    profile_image_url: Optional[str]
    liked_at: datetime


class ChallengePhotoLikedUsersResponse(BaseModel):
    items: list[ChallengePhotoLikedUserItem]
    total: int
    limit: int
    offset: int
