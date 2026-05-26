"""챌린지 인증 사진 라우터."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import CommonResponse
from app.db import get_db
from app.models import User
from app.schemas.challenge import ChallengePhotoLikedUsersResponse, ChallengePhotoLikeResponse
from app.services.auth_service import get_current_user
from app.services.challenge_photo_service import ChallengePhotoService
from app.services.storage import FileStorage, get_file_storage


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]


@router.post("/{photo_id}/like", response_model=CommonResponse[ChallengePhotoLikeResponse])
def like_challenge_photo(
    photo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[ChallengePhotoLikeResponse]:
    result = ChallengePhotoService(db).like_photo(
        user_id=current_user.id,
        photo_id=photo_id,
    )
    return CommonResponse.success_response(
        message="좋아요가 등록되었습니다.",
        data=result,
    )


@router.delete("/{photo_id}", response_model=CommonResponse[None])
def delete_challenge_photo(
    photo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    storage: Storage,
) -> CommonResponse[None]:
    ChallengePhotoService(db, storage).delete_photo(
        user_id=current_user.id,
        photo_id=photo_id,
    )
    return CommonResponse.success_response(
        message="인증 사진이 삭제되었습니다.",
        data=None,
    )


@router.get("/{photo_id}/likes", response_model=CommonResponse[ChallengePhotoLikedUsersResponse])
def get_challenge_photo_liked_users(
    photo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CommonResponse[ChallengePhotoLikedUsersResponse]:
    """인증된 사용자가 특정 인증 사진의 좋아요 사용자 목록을 조회한다."""

    result = ChallengePhotoService(db).get_liked_users(
        photo_id=photo_id,
        limit=limit,
        offset=offset,
    )
    return CommonResponse.success_response(
        message="좋아요 사용자 목록 조회 성공",
        data=result,
    )
