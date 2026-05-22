"""Chat session service logic."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatSession


from app.common.exceptions.custom import ChatSessionNotFoundException as ChatSessionNotFound


def parse_cursor(cursor: str | None) -> datetime | None:
    if cursor is None:
        return None
    try:
        return datetime.fromisoformat(cursor)
    except ValueError:
        return None


def _cursor_from_datetime(value: datetime) -> str:
    return value.isoformat()


def create_session(db: Session, *, user_id: UUID) -> ChatSession:
    session = ChatSession(user_id=user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_owned_session(db: Session, *, user_id: UUID, session_id: UUID) -> ChatSession:
    session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    if session is None:
        raise ChatSessionNotFound
    return session


def list_sessions(
    db: Session,
    *,
    user_id: UUID,
    limit: int,
    cursor: str | None,
) -> tuple[list[ChatSession], str | None]:
    cursor_datetime = parse_cursor(cursor)
    query = select(ChatSession).where(ChatSession.user_id == user_id)
    if cursor_datetime is not None:
        query = query.where(ChatSession.updated_at < cursor_datetime)

    rows = list(
        db.scalars(
            query.order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc()).limit(limit + 1)
        )
    )
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _cursor_from_datetime(rows[-1].updated_at)
    return rows, next_cursor


def update_session_title(
    db: Session,
    *,
    user_id: UUID,
    session_id: UUID,
    title: str | None,
) -> ChatSession:
    session = get_owned_session(db, user_id=user_id, session_id=session_id)
    session.title = title
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, *, user_id: UUID, session_id: UUID) -> None:
    session = get_owned_session(db, user_id=user_id, session_id=session_id)
    db.delete(session)
    db.commit()
