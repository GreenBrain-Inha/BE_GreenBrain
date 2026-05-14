"""Chat routes."""

from __future__ import annotations

from typing import Annotated, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageListResponse,
    ChatRequest,
    ChatResponse,
)
from app.schemas.chat_session import (
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from app.schemas.common import Errors, error_response
from app.services import chat as chat_service
from app.services import chat_session as chat_session_service
from app.core.security import ACCESS_TOKEN_COOKIE_NAME, JWT_ALGORITHM, get_jwt_secret
from app.services.chat_session import ChatSessionNotFound
from app.services.token_account import TokenExhausted


router = APIRouter()


DbSession = Annotated[Session, Depends(get_db)]
AccessTokenCookie = Annotated[Optional[str], Cookie(alias=ACCESS_TOKEN_COOKIE_NAME)]


def get_current_user(
    db: DbSession,
    access_token: AccessTokenCookie = None,
) -> User:
    _unauthorized = HTTPException(
        status_code=Errors.NOT_AUTHENTICATED.status_code,
        detail=Errors.NOT_AUTHENTICATED.message,
    )
    if access_token is None:
        raise _unauthorized
    try:
        payload = jwt.decode(access_token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError, JWTError):
        raise _unauthorized
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise _unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=ChatSessionResponse,
)
def create_chat_session(
    current_user: CurrentUser,
    db: DbSession,
) -> ChatSessionResponse:
    session = chat_session_service.create_session(db, user_id=current_user.id)
    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Optional[str] = None,
) -> ChatSessionListResponse:
    sessions, next_cursor = chat_session_service.list_sessions(
        db,
        user_id=current_user.id,
        limit=limit,
        cursor=cursor,
    )
    return ChatSessionListResponse(
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
    )


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_chat_session(
    session_id: UUID,
    payload: ChatSessionUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Union[ChatSessionResponse, JSONResponse]:
    try:
        session = chat_session_service.update_session_title(
            db,
            user_id=current_user.id,
            session_id=session_id,
            title=payload.title,
        )
    except ChatSessionNotFound:
        return error_response(Errors.CHAT_SESSION_NOT_FOUND)

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_chat_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Union[Response, JSONResponse]:
    try:
        chat_session_service.delete_session(db, user_id=current_user.id, session_id=session_id)
    except ChatSessionNotFound:
        return error_response(Errors.CHAT_SESSION_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
def send_chat_message(
    session_id: UUID,
    payload: ChatRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Union[ChatResponse, JSONResponse]:
    try:
        user_message, response_message, tokens_remaining, exhausted, session_title = (
            chat_service.send_message(
                db,
                user_id=current_user.id,
                session_id=session_id,
                message=payload.message,
            )
        )
    except ChatSessionNotFound:
        return error_response(Errors.CHAT_SESSION_NOT_FOUND)
    except TokenExhausted:
        return error_response(Errors.TOKEN_EXHAUSTED)
    except chat_service.AiProviderError:
        return error_response(Errors.AI_PROVIDER_ERROR)

    return ChatResponse(
        message_id=user_message.id,
        response_message_id=response_message.id,
        response=response_message.content,
        carbon_gco2eq=response_message.carbon_gco2eq,
        tokens_remaining=tokens_remaining,
        exhausted=exhausted,
        session_title=session_title,
    )


@router.get("/sessions/{session_id}/messages", response_model=ChatMessageListResponse)
def list_chat_messages(
    session_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Optional[str] = None,
) -> Union[ChatMessageListResponse, JSONResponse]:
    try:
        messages, next_cursor = chat_service.list_messages(
            db,
            user_id=current_user.id,
            session_id=session_id,
            limit=limit,
            cursor=cursor,
        )
    except ChatSessionNotFound:
        return error_response(Errors.CHAT_SESSION_NOT_FOUND)

    return ChatMessageListResponse(
        items=[
            ChatMessageItem(
                id=message.id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                carbon_gco2eq=message.carbon_gco2eq,
                created_at=message.created_at,
            )
            for message in messages
        ],
        next_cursor=next_cursor,
    )
