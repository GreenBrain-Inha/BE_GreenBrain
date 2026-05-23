"""Chat routes."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Query, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions.custom import NotAuthenticatedException
from app.common.response import CommonResponse
from app.db import get_db
from app.models import User
from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageListResponse,
    ChatModelListResponse,
    ChatRequest,
    ChatResponse,
)
from app.schemas.chat_session import (
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from app.services import chat as chat_service
from app.services import chat_session as chat_session_service
from app.core.security import ACCESS_TOKEN_COOKIE_NAME, JWT_ALGORITHM, get_jwt_secret


router = APIRouter()


DbSession = Annotated[Session, Depends(get_db)]
AccessTokenCookie = Annotated[Optional[str], Cookie(alias=ACCESS_TOKEN_COOKIE_NAME)]


def get_current_user(
    db: DbSession,
    access_token: AccessTokenCookie = None,
) -> User:
    if access_token is None:
        raise NotAuthenticatedException()
    try:
        payload = jwt.decode(access_token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError, JWTError):
        raise NotAuthenticatedException()
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise NotAuthenticatedException()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/models", response_model=CommonResponse[ChatModelListResponse])
def list_chat_models(current_user: CurrentUser) -> CommonResponse[ChatModelListResponse]:
    return CommonResponse.success_response(
        message="조회 성공",
        data=ChatModelListResponse(items=chat_service.list_models()),
    )


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=CommonResponse[ChatSessionResponse],
)
def create_chat_session(
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[ChatSessionResponse]:
    session = chat_session_service.create_session(db, user_id=current_user.id)
    return CommonResponse.success_response(
        message="세션이 생성되었습니다.",
        data=ChatSessionResponse(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
        ),
    )


@router.get("/sessions", response_model=CommonResponse[ChatSessionListResponse])
def list_chat_sessions(
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Optional[str] = None,
) -> CommonResponse[ChatSessionListResponse]:
    sessions, next_cursor = chat_session_service.list_sessions(
        db,
        user_id=current_user.id,
        limit=limit,
        cursor=cursor,
    )
    return CommonResponse.success_response(
        message="조회 성공",
        data=ChatSessionListResponse(
            items=[
                ChatSessionResponse(
                    id=session.id,
                    title=session.title,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                )
                for session in sessions
            ],
            next_cursor=next_cursor,
        ),
    )


@router.patch("/sessions/{session_id}", response_model=CommonResponse[ChatSessionResponse])
def update_chat_session(
    session_id: UUID,
    payload: ChatSessionUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[ChatSessionResponse]:
    session = chat_session_service.update_session_title(
        db,
        user_id=current_user.id,
        session_id=session_id,
        title=payload.title,
    )
    return CommonResponse.success_response(
        message="수정되었습니다.",
        data=ChatSessionResponse(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
        ),
    )


@router.delete("/sessions/{session_id}", response_model=CommonResponse[None])
def delete_chat_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[None]:
    chat_session_service.delete_session(db, user_id=current_user.id, session_id=session_id)
    return CommonResponse.success_response("세션이 삭제되었습니다.")


@router.post("/sessions/{session_id}/messages", response_model=CommonResponse[ChatResponse])
def send_chat_message(
    session_id: UUID,
    payload: ChatRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> CommonResponse[ChatResponse]:
    user_message, response_message, tokens_remaining, exhausted, session_title = (
        chat_service.send_message(
            db,
            user_id=current_user.id,
            session_id=session_id,
            message=payload.message,
            model_id=payload.model_id,
        )
    )
    return CommonResponse.success_response(
        message="메시지가 전송되었습니다.",
        data=ChatResponse(
            message_id=user_message.id,
            response_message_id=response_message.id,
            response=response_message.content,
            carbon_gco2eq=response_message.carbon_gco2eq,
            tokens_remaining=tokens_remaining,
            exhausted=exhausted,
            session_title=session_title,
            model_id=response_message.model_id or chat_service.DEFAULT_CHAT_MODEL,
        ),
    )


@router.get("/sessions/{session_id}/messages", response_model=CommonResponse[ChatMessageListResponse])
def list_chat_messages(
    session_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Optional[str] = None,
) -> CommonResponse[ChatMessageListResponse]:
    messages, next_cursor = chat_service.list_messages(
        db,
        user_id=current_user.id,
        session_id=session_id,
        limit=limit,
        cursor=cursor,
    )
    return CommonResponse.success_response(
        message="조회 성공",
        data=ChatMessageListResponse(
            items=[
                ChatMessageItem(
                    id=message.id,
                    session_id=message.session_id,
                    role=message.role,
                    content=message.content,
                    carbon_gco2eq=message.carbon_gco2eq,
                    model_id=message.model_id,
                    created_at=message.created_at,
                )
                for message in messages
            ],
            next_cursor=next_cursor,
        ),
    )
