"""Token state routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import CommonResponse
from app.db import get_db
from app.models import User
from app.schemas.token import TokenStateResponse
from app.services.auth_service import get_current_user
from app.services.token_service import TokenService


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/today", response_model=CommonResponse[TokenStateResponse])
def get_today_token_state(
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[TokenStateResponse]:
    state = TokenService(db).get_today_state(current_user.id)
    return CommonResponse.success_response(
        message="조회 성공",
        data=TokenStateResponse.model_validate(state),
    )
