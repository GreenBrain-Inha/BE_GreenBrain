"""Token state routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.token import TokenStateResponse
from app.services.auth import get_current_user
from app.services.daily_reset import get_or_create_today_state


router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/today", response_model=TokenStateResponse)
def get_today_token_state(
    current_user: CurrentUser,
    db: DbSession,
) -> TokenStateResponse:
    state = get_or_create_today_state(db, current_user.id)
    db.commit()
    db.refresh(state)
    return TokenStateResponse.model_validate(state)
