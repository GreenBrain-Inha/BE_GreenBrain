"""User API schemas."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


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
    nickname: Optional[str] = None
    profile_image_url: Optional[str] = None


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
