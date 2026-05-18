"""Challenge routes."""

from __future__ import annotations

from typing import Annotated, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Challenge, ChallengePhoto, Like, User
from app.schemas.challenge import (
    AcceptChallengeResponse,
    ChallengeFeedItemResponse,
    ChallengeFeedResponse,
    ChallengePhotoResponse,
    ChallengePhotoUploadChallengeResponse,
    ChallengePhotoUploadResponse,
    ChallengePhotoUploadRewardResponse,
    ChallengeResponse,
    CurrentChallengeResponse,
    GenerateChallengeResponse,
)
from app.schemas.common import Errors, error_response
from app.services.auth import get_current_user
from app.services import challenge_gen, challenge_photo
from app.services.storage import FileStorage, get_file_storage


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]


@router.get("/current", response_model=CurrentChallengeResponse)
def get_current_challenge(
    current_user: CurrentUser,
    db: DbSession,
) -> CurrentChallengeResponse:
    challenge = challenge_gen.get_current_challenge(db, user_id=current_user.id)
    return CurrentChallengeResponse(
        challenge=ChallengeResponse.model_validate(challenge) if challenge else None
    )


@router.get("/feed", response_model=ChallengeFeedResponse)
def get_challenge_feed(
    current_user: CurrentUser,
    db: DbSession,
    storage: Storage,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChallengeFeedResponse:
    like_counts = (
        select(
            Like.photo_id.label("photo_id"),
            func.count(Like.id).label("like_count"),
        )
        .group_by(Like.photo_id)
        .subquery()
    )
    liked_by_me = (
        select(Like.photo_id.label("photo_id"))
        .where(Like.liker_user_id == current_user.id)
        .subquery()
    )
    total = db.scalar(select(func.count()).select_from(ChallengePhoto)) or 0
    rows = db.execute(
        select(
            ChallengePhoto,
            Challenge,
            User,
            func.coalesce(like_counts.c.like_count, 0),
            liked_by_me.c.photo_id.is_not(None),
        )
        .join(Challenge, Challenge.id == ChallengePhoto.challenge_id)
        .join(User, User.id == ChallengePhoto.user_id)
        .outerjoin(like_counts, like_counts.c.photo_id == ChallengePhoto.id)
        .outerjoin(liked_by_me, liked_by_me.c.photo_id == ChallengePhoto.id)
        .order_by(ChallengePhoto.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return ChallengeFeedResponse(
        items=[
            ChallengeFeedItemResponse(
                photo_id=photo.id,
                challenge_id=photo.challenge_id,
                user_id=user.id,
                nickname=user.nickname,
                profile_image_url=user.profile_image_url,
                title=challenge.title,
                category=challenge.category,
                photo_url=storage.get_url(photo.file_path),
                like_count=int(like_count),
                liked_by_me=bool(liked),
                carbon_saved_gco2eq=None,
                created_at=photo.created_at,
            )
            for photo, challenge, user, like_count, liked in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    response_model=GenerateChallengeResponse,
)
def generate_challenge(
    current_user: CurrentUser,
    db: DbSession,
    response: Response,
) -> Union[GenerateChallengeResponse, JSONResponse]:
    try:
        challenge, created = challenge_gen.generate_challenge(db, user_id=current_user.id)
    except challenge_gen.TokenNotExhausted:
        return error_response(Errors.TOKEN_NOT_EXHAUSTED)
    except challenge_gen.DailyChallengeLimitReached:
        return error_response(Errors.DAILY_CHALLENGE_LIMIT_REACHED)
    except challenge_gen.ChallengeGenerationFailed:
        return error_response(Errors.CHALLENGE_GENERATION_FAILED)

    if not created:
        response.status_code = status.HTTP_200_OK

    return GenerateChallengeResponse(
        challenge=ChallengeResponse.model_validate(challenge),
        created=created,
    )


@router.post("/{challenge_id}/accept", response_model=AcceptChallengeResponse)
def accept_challenge(
    challenge_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Union[AcceptChallengeResponse, JSONResponse]:
    try:
        challenge = challenge_gen.accept_challenge(
            db,
            user_id=current_user.id,
            challenge_id=challenge_id,
        )
    except challenge_gen.ChallengeNotFound:
        return error_response(Errors.CHALLENGE_NOT_FOUND)
    except challenge_gen.ChallengeNotPending:
        return error_response(Errors.CHALLENGE_NOT_PENDING)

    return AcceptChallengeResponse(challenge=ChallengeResponse.model_validate(challenge))


@router.post(
    "/{challenge_id}/photo",
    status_code=status.HTTP_201_CREATED,
    response_model=ChallengePhotoUploadResponse,
)
def upload_challenge_photo(
    challenge_id: UUID,
    file: UploadFile,
    current_user: CurrentUser,
    db: DbSession,
    storage: Storage,
) -> Union[ChallengePhotoUploadResponse, JSONResponse]:
    try:
        result = challenge_photo.upload_challenge_photo(
            db,
            user_id=current_user.id,
            challenge_id=challenge_id,
            upload=file,
            storage=storage,
        )
    except challenge_photo.ChallengeNotFound:
        return error_response(Errors.CHALLENGE_NOT_FOUND)
    except challenge_photo.ChallengeNotOwned:
        return error_response(Errors.CHALLENGE_NOT_OWNED)
    except challenge_photo.ChallengeNotActive:
        return error_response(Errors.CHALLENGE_NOT_ACTIVE)
    except challenge_photo.PhotoAlreadyUploaded:
        return error_response(Errors.PHOTO_ALREADY_UPLOADED)
    except challenge_photo.FileTooLarge:
        return error_response(Errors.FILE_TOO_LARGE)
    except challenge_photo.UnsupportedImageType:
        return error_response(Errors.UNSUPPORTED_IMAGE_TYPE)
    except challenge_photo.InvalidImage:
        return error_response(Errors.INVALID_IMAGE)
    except challenge_photo.StorageFailed:
        return error_response(Errors.STORAGE_WRITE_FAILED)

    return ChallengePhotoUploadResponse(
        photo=ChallengePhotoResponse(
            id=result.photo.id,
            challenge_id=result.photo.challenge_id,
            file_url=result.file_url,
            created_at=result.photo.created_at,
        ),
        challenge=ChallengePhotoUploadChallengeResponse(
            id=result.challenge.id,
            status=result.challenge.status,
            completed_at=result.challenge.completed_at,
        ),
        reward=ChallengePhotoUploadRewardResponse(
            type="upload_reward",
            reward_amount=result.reward_amount,
            tokens_remaining=result.tokens_remaining,
        ),
    )
