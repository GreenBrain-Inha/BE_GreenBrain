"""Challenge photo routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import CommonResponse
from app.db import get_db
from app.models import User
from app.schemas.challenge import ChallengePhotoLikeResponse
from app.services.auth_service import get_current_user
from app.services.challenge_photo_service import ChallengePhotoService


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


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
