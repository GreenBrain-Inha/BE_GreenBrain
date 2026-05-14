"""User routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserProfile
from app.schemas.common import Errors, error_response
from app.schemas.user import (
    UserMeResponse,
    UserMeUpdateRequest,
    UserOnboardingRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.auth import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserMeResponse:
    return UserMeResponse.model_validate(current_user)


@router.patch("/me", response_model=UserMeResponse)
def update_me(
    payload: UserMeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    if payload.nickname is not None:
        current_user.nickname = payload.nickname
    if payload.profile_image_url is not None:
        current_user.profile_image_url = payload.profile_image_url

    db.commit()
    db.refresh(current_user)
    return UserMeResponse.model_validate(current_user)


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse | JSONResponse:
    if current_user.profile is None:
        return error_response(Errors.NOT_FOUND)
    return UserProfileResponse.model_validate(current_user.profile)


@router.patch("/profile", response_model=UserProfileResponse)
def update_profile(
    payload: UserProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse | JSONResponse:
    if current_user.profile is None:
        return error_response(Errors.NOT_FOUND)

    profile = current_user.profile
    if payload.transport_mode is not None:
        profile.transport_mode = payload.transport_mode
    if payload.diet_type is not None:
        profile.diet_type = payload.diet_type
    if payload.housing_type is not None:
        profile.housing_type = payload.housing_type

    db.commit()
    db.refresh(profile)
    return UserProfileResponse.model_validate(profile)


@router.post("/onboarding", status_code=status.HTTP_201_CREATED, response_model=UserProfileResponse)
def onboarding(
    payload: UserOnboardingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    if current_user.profile is None:
        profile = UserProfile(
            user_id=current_user.id,
            transport_mode=payload.transport_mode,
            diet_type=payload.diet_type,
            housing_type=payload.housing_type,
        )
        db.add(profile)
    else:
        profile = current_user.profile
        profile.transport_mode = payload.transport_mode
        profile.diet_type = payload.diet_type
        profile.housing_type = payload.housing_type

    db.commit()
    db.refresh(profile)
    return UserProfileResponse.model_validate(profile)
