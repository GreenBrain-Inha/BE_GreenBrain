"""User API schemas."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
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


class TransportMode(str, Enum):
    car = "car"
    transit = "transit"
    walk = "walk"
    bike = "bike"
    mixed = "mixed"


class DietType(str, Enum):
    omnivore = "omnivore"
    vegetarian = "vegetarian"
    vegan = "vegan"
    flexitarian = "flexitarian"


class HousingType(str, Enum):
    apartment = "apartment"
    house = "house"
    studio = "studio"
    dorm = "dorm"
    other = "other"


class UserProfileResponse(BaseModel):
    transport_mode: TransportMode
    diet_type: DietType
    housing_type: HousingType
    updated_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdateRequest(BaseModel):
    transport_mode: Optional[TransportMode] = None
    diet_type: Optional[DietType] = None
    housing_type: Optional[HousingType] = None


class UserOnboardingRequest(BaseModel):
    transport_mode: TransportMode
    diet_type: DietType
    housing_type: HousingType


UserMeResponse.model_rebuild()
