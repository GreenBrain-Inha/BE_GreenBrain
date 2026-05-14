"""User API schemas."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UserMeResponse(BaseModel):
    id: UUID
    email: str
    nickname: Optional[str]
    profile_image_url: Optional[str]

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
