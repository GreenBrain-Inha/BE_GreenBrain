"""Challenge routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.response import CommonResponse
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
from app.services.auth_service import get_current_user
from app.services import challenge_photo
from app.services.challenge_service import ChallengeService
from app.services.storage import FileStorage, get_file_storage


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]


@router.get("/current", response_model=CommonResponse[CurrentChallengeResponse])
def get_current_challenge(
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[CurrentChallengeResponse]:
    challenge = ChallengeService(db).get_current(current_user.id)
    return CommonResponse.success_response(
        message="조회 성공",
        data=CurrentChallengeResponse(
            challenge=ChallengeResponse.model_validate(challenge) if challenge else None
        ),
    )


@router.get("/feed", response_model=CommonResponse[ChallengeFeedResponse])
def get_challenge_feed(
    current_user: CurrentUser,
    db: DbSession,
    storage: Storage,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CommonResponse[ChallengeFeedResponse]:
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

    return CommonResponse.success_response(
        message="조회 성공",
        data=ChallengeFeedResponse(
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
        ),
    )


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    response_model=CommonResponse[GenerateChallengeResponse],
)
def generate_challenge(
    current_user: CurrentUser,
    db: DbSession,
    response: Response,
) -> CommonResponse[GenerateChallengeResponse]:
    challenge, created = ChallengeService(db).generate(current_user.id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return CommonResponse.success_response(
        message="챌린지가 생성되었습니다." if created else "기존 챌린지를 반환합니다.",
        data=GenerateChallengeResponse(
            challenge=ChallengeResponse.model_validate(challenge),
            created=created,
        ),
    )


@router.post("/{challenge_id}/accept", response_model=CommonResponse[AcceptChallengeResponse])
def accept_challenge(
    challenge_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[AcceptChallengeResponse]:
    challenge = ChallengeService(db).accept(current_user.id, challenge_id)
    return CommonResponse.success_response(
        message="챌린지를 수락했습니다.",
        data=AcceptChallengeResponse(challenge=ChallengeResponse.model_validate(challenge)),
    )


@router.post(
    "/{challenge_id}/photo",
    status_code=status.HTTP_201_CREATED,
    response_model=CommonResponse[ChallengePhotoUploadResponse],
)
def upload_challenge_photo(
    challenge_id: UUID,
    file: UploadFile,
    current_user: CurrentUser,
    db: DbSession,
    storage: Storage,
) -> CommonResponse[ChallengePhotoUploadResponse]:
    result = challenge_photo.upload_challenge_photo(
        db,
        user_id=current_user.id,
        challenge_id=challenge_id,
        upload=file,
        storage=storage,
    )
    return CommonResponse.success_response(
        message="사진이 업로드되었습니다.",
        data=ChallengePhotoUploadResponse(
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
        ),
    )
