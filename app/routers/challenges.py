"""Challenge routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.common.response import CommonResponse
from app.db import get_db
from app.models import User
from app.schemas.challenge import (
    AcceptChallengeResponse,
    ChallengeFeedResponse,
    ChallengePhotoUploadResponse,
    ChallengeResponse,
    CurrentChallengeResponse,
    GenerateChallengeResponse,
)
from app.services.auth_service import get_current_user
from app.services.challenge_photo_service import ChallengePhotoService
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
    result = ChallengePhotoService(db, storage).get_feed(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return CommonResponse.success_response(
        message="조회 성공",
        data=result,
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
    result = ChallengePhotoService(db, storage).upload_photo(
        user_id=current_user.id,
        challenge_id=challenge_id,
        file=file,
    )
    return CommonResponse.success_response(
        message="사진이 업로드되었습니다.",
        data=result,
    )
