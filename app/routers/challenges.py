"""Challenge routes."""

from __future__ import annotations

from typing import Annotated, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.challenge import (
    AcceptChallengeResponse,
    ChallengeResponse,
    CurrentChallengeResponse,
    GenerateChallengeResponse,
)
from app.schemas.common import Errors, error_response
from app.services.auth import get_current_user
from app.services import challenge_gen


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/current", response_model=CurrentChallengeResponse)
def get_current_challenge(
    current_user: CurrentUser,
    db: DbSession,
) -> CurrentChallengeResponse:
    challenge = challenge_gen.get_current_challenge(db, user_id=current_user.id)
    return CurrentChallengeResponse(
        challenge=ChallengeResponse.model_validate(challenge) if challenge else None
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
