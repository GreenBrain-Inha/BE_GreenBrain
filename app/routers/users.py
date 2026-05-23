"""User routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.common.exceptions.custom import InvalidFieldException
from app.common.response import CommonResponse
from app.db import get_db
from app.models import User
from app.schemas.user import (
    TodayTokensSummaryResponse,
    UserMeResponse,
    UserMeUpdateResponse,
    UserOnboardingRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.auth_service import get_current_user
from app.services.storage import FileStorage, get_file_storage
from app.services.user_service import UserService

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]


@router.get("/me", response_model=CommonResponse[UserMeResponse])
def get_me(
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[UserMeResponse]:
    user, state = UserService(db).get_me(current_user)
    return CommonResponse.success_response(
        message="조회 성공",
        data=UserMeResponse(
            id=user.id,
            email=user.email,
            nickname=user.nickname,
            profile_image_url=user.profile_image_url,
            onboarding_completed=user.profile is not None,
            profile=UserProfileResponse.model_validate(user.profile) if user.profile else None,
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

    updated_user = UserService(db, storage).update_me(
        current_user,
        nickname=nickname,
        profile_image=profile_image,
    )
    return CommonResponse.success_response(
        message="수정되었습니다.",
        data=UserMeUpdateResponse.model_validate(updated_user),
    )


@router.get("/profile", response_model=CommonResponse[UserProfileResponse])
def get_profile(
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[UserProfileResponse]:
    profile = UserService(db).get_profile(current_user)
    return CommonResponse.success_response(
        message="조회 성공",
        data=UserProfileResponse.model_validate(profile),
    )


@router.patch("/profile", response_model=CommonResponse[UserProfileResponse])
def update_profile(
    payload: UserProfileUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> CommonResponse[UserProfileResponse]:
    profile = UserService(db).update_profile(
        current_user,
        transport_mode=payload.transport_mode,
        diet_type=payload.diet_type,
        housing_type=payload.housing_type,
    )
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
    profile = UserService(db).complete_onboarding(
        current_user,
        transport_mode=payload.transport_mode,
        diet_type=payload.diet_type,
        housing_type=payload.housing_type,
    )
    return CommonResponse.success_response(
        message="온보딩이 완료되었습니다.",
        data=UserProfileResponse.model_validate(profile),
    )
