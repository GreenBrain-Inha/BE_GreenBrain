"""User API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import AnyUrl, BaseModel, Field


class TodayTokensSummaryResponse(BaseModel):
    date: date
    tokens_remaining: float


class UserMeResponse(BaseModel):
    id: UUID
    email: str
    nickname: Optional[str]
    profile_image_url: Optional[str]
    onboarding_completed: bool
    profile: Optional[UserProfileResponse] = None
    today_tokens: TodayTokensSummaryResponse

    class Config:
        from_attributes = True


class UserMeUpdateRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, min_length=1)
    profile_image_url: Optional[AnyUrl] = None


class UserMeUpdateResponse(BaseModel):
    id: UUID
    email: str
    nickname: Optional[str]
    profile_image_url: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    transport_mode: str
    diet_type: str
    housing_type: str

    class Config:
        from_attributes = True


class UserProfileUpdateRequest(BaseModel):
    transport_mode: Optional[str] = None
    diet_type: Optional[str] = None
    housing_type: Optional[str] = None


class UserOnboardingRequest(BaseModel):
    transport_mode: str
    diet_type: str
    housing_type: str


UserMeResponse.model_rebuild()
