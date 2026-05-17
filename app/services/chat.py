"""Chat orchestration service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ecologits import EcoLogits
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message
from app.services.carbon import carbon_gco2eq_from_openai_response
from app.services.chat_session import get_owned_session, parse_cursor
from app.services.daily_reset import get_or_create_today_state
from app.services.token_account import TokenExhausted, deduct_chat_usage, ensure_chat_tokens_available


CHAT_MODEL = "gpt-4o-mini"
EcoLogits.init(providers=["openai"])


class AiProviderError(Exception):
    """Raised when the AI provider cannot produce a response."""


def _openai_client() -> OpenAI:
    from app.core.config import settings
    try:
        return OpenAI(api_key=settings.openai_api_key)
    except RuntimeError:
        raise AiProviderError


def _build_history(db: Session, *, session_id: UUID, latest_message: str) -> list[dict[str, str]]:
    rows = list(db.scalars(
        select(Message)
        .where(Message.session_id == session_id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at.desc())
        .limit(20)
    ))
    history = [{"role": m.role, "content": m.content} for m in reversed(rows)]
    if not history or history[-1] != {"role": "user", "content": latest_message}:
        history.append({"role": "user", "content": latest_message})
    return history


def generate_ai_response(
    db: Session,
    *,
    session_id: UUID,
    message: str,
) -> tuple[str, float | None]:
    try:
        response = _openai_client().chat.completions.create(
            model=CHAT_MODEL,
            messages=_build_history(db, session_id=session_id, latest_message=message),
        )
    except OpenAIError as exc:
        raise AiProviderError from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise AiProviderError
    return content, carbon_gco2eq_from_openai_response(response)


def _generate_title(message: str) -> str | None:
    try:
        response = _openai_client().chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Create a short Korean chat title. Return only the title.",
                },
                {"role": "user", "content": message},
            ],
            max_tokens=20,
        )
    except (AiProviderError, OpenAIError):
        return None

    title = response.choices[0].message.content if response.choices else None
    if title is None:
        return None
    return title.strip()[:30] or None


def _fallback_title(message: str) -> str:
    return message.strip()[:30]


def send_message(
    db: Session,
    *,
    user_id: UUID,
    session_id: UUID,
    message: str,
) -> tuple[Message, Message, float, bool, str | None]:
    session = get_owned_session(db, user_id=user_id, session_id=session_id)
    state = get_or_create_today_state(db, user_id)
    ensure_chat_tokens_available(state)

    user_message = Message(
        user_id=user_id,
        session_id=session.id,
        role="user",
        content=message,
    )
    db.add(user_message)
    db.flush()

    try:
        response_text, carbon_gco2eq = generate_ai_response(db, session_id=session.id, message=message)
    except AiProviderError:
        db.rollback()
        raise

    response_message = Message(
        user_id=user_id,
        session_id=session.id,
        role="assistant",
        content=response_text,
        carbon_gco2eq=carbon_gco2eq,
    )
    db.add(response_message)
    db.flush()

    exhausted = deduct_chat_usage(
        db,
        state=state,
        user_id=user_id,
        message_id=response_message.id,
        carbon_gco2eq=carbon_gco2eq,
    )

    session_title = None
    if session.title is None:
        session_title = _generate_title(message) or _fallback_title(message)
        session.title = session_title
    session.updated_at = datetime.now(timezone.utc)

    tokens_remaining = state.tokens_remaining
    db.commit()
    db.refresh(user_message)
    db.refresh(response_message)
    return user_message, response_message, tokens_remaining, exhausted, session_title


def list_messages(
    db: Session,
    *,
    user_id: UUID,
    session_id: UUID,
    limit: int,
    cursor: str | None,
) -> tuple[list[Message], str | None]:
    session = get_owned_session(db, user_id=user_id, session_id=session_id)
    cursor_datetime = parse_cursor(cursor)

    query = select(Message).where(Message.session_id == session.id)
    if cursor_datetime is not None:
        query = query.where(Message.created_at < cursor_datetime)

    rows = list(db.scalars(query.order_by(Message.created_at.desc()).limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].created_at.isoformat()

    return list(reversed(rows)), next_cursor
