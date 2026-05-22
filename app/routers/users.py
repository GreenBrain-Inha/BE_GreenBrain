"""User routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.common.exceptions.custom import InvalidFieldException, NotFoundException
from app.common.response import CommonResponse
from app.db import get_db
from app.models import User, UserProfile
from app.schemas.user import (
    TodayTokensSummaryResponse,
    UserMeResponse,
    UserMeUpdateResponse,
    UserOnboardingRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.auth import get_current_user
from app.services.daily_reset import get_or_create_today_state
from app.services import user_profile
from app.services.storage import FileStorage, get_file_storage

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]


@router.get("/me", response_model=CommonResponse[UserMeResponse])
def get_me(
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[UserMeResponse]:
    state = get_or_create_today_state(db, current_user.id)
    db.commit()
    db.refresh(state)
    return CommonResponse.success_response(
        message="조회 성공",
        data=UserMeResponse(
            id=current_user.id,
            email=current_user.email,
            nickname=current_user.nickname,
            profile_image_url=current_user.profile_image_url,
            onboarding_completed=current_user.profile is not None,
            profile=UserProfileResponse.model_validate(current_user.profile) if current_user.profile else None,
            today_tokens=TodayTokensSummaryResponse(date=state.date, tokens_remaining=state.tokens_remaining),
        ),
    )


@router.patch("/me", response_model=CommonResponse[UserMeUpdateResponse])
async def update_me(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    storage: Storage,
    nickname: Annotated[str | None, Form(min_length=1)] = None,
    profile_image: Annotated[UploadFile | None, File()] = None,
) -> CommonResponse[UserMeUpdateResponse]:
    form = await request.form()
    if form.get("nickname") == "":
        raise InvalidFieldException(message="닉네임은 비워둘 수 없습니다.")

    updated_user = user_profile.update_user_profile(
        db,
        user=current_user,
        nickname=nickname,
        profile_image=profile_image,
        storage=storage,
    )
    return CommonResponse.success_response(
        message="수정되었습니다.",
        data=UserMeUpdateResponse.model_validate(updated_user),
    )


@router.get("/profile", response_model=CommonResponse[UserProfileResponse])
def get_profile(
    current_user: CurrentUser,
) -> CommonResponse[UserProfileResponse]:
    if current_user.profile is None:
        raise NotFoundException()
    return CommonResponse.success_response(
        message="조회 성공",
        data=UserProfileResponse.model_validate(current_user.profile),
    )


@router.patch("/profile", response_model=CommonResponse[UserProfileResponse])
def update_profile(
    payload: UserProfileUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> CommonResponse[UserProfileResponse]:
    if current_user.profile is None:
        raise NotFoundException()

    profile = current_user.profile
    if payload.transport_mode is not None:
        profile.transport_mode = payload.transport_mode
    if payload.diet_type is not None:
        profile.diet_type = payload.diet_type
    if payload.housing_type is not None:
        profile.housing_type = payload.housing_type

    db.commit()
    db.refresh(profile)
    return CommonResponse.success_response(
        message="수정되었습니다.",
        data=UserProfileResponse.model_validate(profile),
    )


@router.post("/onboarding", status_code=status.HTTP_201_CREATED, response_model=CommonResponse[UserProfileResponse])
def onboarding(
    payload: UserOnboardingRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> CommonResponse[UserProfileResponse]:
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
    return CommonResponse.success_response(
        message="온보딩이 완료되었습니다.",
        data=UserProfileResponse.model_validate(profile),
    )
