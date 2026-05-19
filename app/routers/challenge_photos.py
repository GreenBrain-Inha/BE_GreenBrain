"""Challenge photo routes."""

from __future__ import annotations

from typing import Annotated, Union
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.challenge import ChallengePhotoLikeResponse
from app.schemas.common import Errors, error_response
from app.services import challenge_like
from app.services.auth import get_current_user


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/{photo_id}/like", response_model=ChallengePhotoLikeResponse)
def like_challenge_photo(
    photo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Union[ChallengePhotoLikeResponse, JSONResponse]:
    try:
        like_count = challenge_like.like_challenge_photo(
            db,
            user_id=current_user.id,
            photo_id=photo_id,
        )
    except challenge_like.ChallengePhotoNotFound:
        return error_response(Errors.CHALLENGE_PHOTO_NOT_FOUND)
    except challenge_like.CannotLikeOwnPhoto:
        return error_response(Errors.CANNOT_LIKE_OWN_PHOTO)
    except challenge_like.PhotoAlreadyLiked:
        return error_response(Errors.PHOTO_ALREADY_LIKED)

    return ChallengePhotoLikeResponse(photo_id=photo_id, liked=True, like_count=like_count)
