"""Chat and chat session service logic."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, NoReturn
from uuid import UUID

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions.custom import (
    AiProviderException as AiProviderError,
    AiProviderStatusException,
    ChatSessionNotFoundException as ChatSessionNotFound,
    UnsupportedChatModelException as UnsupportedChatModel,
)
from app.models import ChatSession, Message
from app.services.carbon import carbon_gco2eq_from_model_usage
from app.services.token_service import TokenService


logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "openai/gpt-4.1-2025-04-14"
TITLE_MODEL = DEFAULT_CHAT_MODEL
_ALLOWED_PROVIDERS = frozenset({"openai", "anthropic", "gemini", "google"})


def parse_cursor(cursor: str | None) -> datetime | None:
    """페이지네이션 cursor를 datetime으로 변환하고, 잘못된 값은 무시한다."""

    if cursor is None:
        return None
    try:
        return datetime.fromisoformat(cursor)
    except ValueError:
        return None


def _cursor_from_datetime(value: datetime) -> str:
    """datetime 값을 cursor 응답에 사용할 ISO 문자열로 변환한다."""

    return value.isoformat()


def resolve_chat_model(model_id: str | None) -> str:
    """요청 모델 ID를 검증하고, 없으면 기본 채팅 모델을 반환한다."""

    model = (model_id or DEFAULT_CHAT_MODEL).strip()
    provider, sep, model_name = model.partition("/")
    if sep and model_name and provider in _ALLOWED_PROVIDERS:
        return model
    raise UnsupportedChatModel


def _openai_client() -> OpenAI:
    """RunYourAI 호환 OpenAI client를 생성한다."""

    from app.core.config import settings

    try:
        return OpenAI(
            api_key=settings.runyour_api_key,
            base_url="https://api.runyour.ai/v1",
        )
    except RuntimeError:
        raise AiProviderError


def _extract_provider_error_message(exc: APIStatusError) -> str:
    """AI provider 오류 응답에서 클라이언트에 전달할 메시지를 추출한다."""

    body = exc.body
    if isinstance(body, dict):
        # provider 원본 오류 body 전체를 클라이언트에 노출하지 않고,
        # OpenAI 호환 응답에서 사용자에게 의미 있는 message/code/type만 우선 추출한다.
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or error.get("type")
            if message is not None:
                return str(message).strip()
        # 일부 provider는 error를 중첩 객체가 아닌 문자열로 내려주므로 그 값만 사용한다.
        if error is not None:
            return str(error).strip()
        # OpenAI 호환 형식이 아니어도 FastAPI 스타일의 message/detail 응답이면 재사용한다.
        message = body.get("message") or body.get("detail")
        if message is not None:
            return str(message).strip()
    elif body is not None:
        # JSON이 아닌 provider 응답은 구조화할 수 없으므로 문자열 표현만 CommonResponse에 담는다.
        return str(body).strip()

    # body에서 안전한 메시지를 찾지 못한 경우 SDK 예외 문자열을 마지막 fallback으로 사용한다.
    return str(exc).strip()


def _ai_provider_status_error(exc: APIStatusError) -> AiProviderStatusException:
    """OpenAI SDK의 HTTP 상태 오류를 앱 도메인 예외로 변환한다."""

    return AiProviderStatusException(
        provider_status_code=exc.status_code,
        provider_message=_extract_provider_error_message(exc),
    )


def _raise_ai_provider_error(exc: OpenAIError) -> NoReturn:
    """OpenAI SDK 예외를 CommonResponse로 처리 가능한 앱 예외로 변환해 발생시킨다."""

    if isinstance(exc, APIStatusError):
        logger.exception("runyour.ai API error: %s", exc)
        raise _ai_provider_status_error(exc) from exc
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        logger.exception("runyour.ai connection error: %s", exc)
        raise AiProviderError(message="AI 제공자 연결에 실패했습니다.") from exc

    logger.exception("runyour.ai SDK error: %s", exc)
    raise AiProviderError from exc


def _create_chat_completion(**kwargs: Any) -> Any:
    """RunYourAI chat completion을 호출하고 provider 예외를 앱 예외로 변환한다."""

    try:
        return _openai_client().chat.completions.create(**kwargs)
    except OpenAIError as exc:
        _raise_ai_provider_error(exc)


def _build_history(db: Session, *, session_id: UUID, latest_message: str) -> list[dict[str, str]]:
    """최근 채팅 메시지를 AI provider 요청용 role/content history로 구성한다."""

    rows = list(
        db.scalars(
            select(Message)
            .where(Message.session_id == session_id, Message.role.in_(["user", "assistant"]))
            .order_by(Message.created_at.desc())
            .limit(20)
        )
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(rows)]
    if not history or history[-1] != {"role": "user", "content": latest_message}:
        history.append({"role": "user", "content": latest_message})
    return history


def generate_ai_response(
    db: Session,
    *,
    session_id: UUID,
    message: str,
    model_id: str,
) -> tuple[str, float | None]:
    """AI 응답을 생성하고 응답 사용량 기반 탄소 배출량을 계산한다."""

    timer_start = time.perf_counter()
    response = _create_chat_completion(
        model=model_id,
        messages=_build_history(db, session_id=session_id, latest_message=message),
    )
    request_latency = time.perf_counter() - timer_start

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise AiProviderError

    output_tokens = getattr(getattr(response, "usage", None), "completion_tokens", None)
    logger.info(
        "MODEL INFO (model=%s latency=%.3fs output_tokens=%s)",
        model_id,
        request_latency,
        output_tokens,
    )
    carbon_gco2eq = carbon_gco2eq_from_model_usage(
        model_id=model_id,
        output_token_count=output_tokens,
        request_latency=request_latency,
    )
    return content, carbon_gco2eq


def _generate_title(message: str) -> str | None:
    """첫 사용자 메시지에서 세션 제목을 생성하고 실패하면 None을 반환한다."""

    try:
        response = _create_chat_completion(
            model=TITLE_MODEL,
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
    """AI 제목 생성 실패 시 첫 메시지 앞 30자를 세션 제목으로 사용한다."""

    return message.strip()[:30]


class ChatSessionService:
    """채팅 세션 CRUD와 사용자 소유권 검사를 담당한다."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: UUID) -> ChatSession:
        """사용자 채팅 세션을 생성하고 DB에 커밋한다."""

        session = ChatSession(user_id=user_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_owned(self, user_id: UUID, session_id: UUID) -> ChatSession:
        """사용자가 소유한 채팅 세션을 반환하고, 없으면 404 예외를 발생시킨다."""

        session = self.db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        if session is None:
            raise ChatSessionNotFound
        return session

    def list(
        self,
        user_id: UUID,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[ChatSession], str | None]:
        """사용자의 채팅 세션을 최근 수정 순서로 페이지네이션 조회한다."""

        cursor_datetime = parse_cursor(cursor)
        query = select(ChatSession).where(ChatSession.user_id == user_id)
        if cursor_datetime is not None:
            query = query.where(ChatSession.updated_at < cursor_datetime)

        rows = list(
            self.db.scalars(
                query.order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc()).limit(
                    limit + 1
                )
            )
        )
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _cursor_from_datetime(rows[-1].updated_at)
        return rows, next_cursor

    def update_title(
        self,
        user_id: UUID,
        session_id: UUID,
        title: str | None,
    ) -> ChatSession:
        """사용자 채팅 세션 제목을 수정하고 DB에 커밋한다."""

        session = self.get_owned(user_id, session_id)
        session.title = title
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete(self, user_id: UUID, session_id: UUID) -> None:
        """사용자 채팅 세션과 cascade 대상 메시지를 삭제하고 DB에 커밋한다."""

        session = self.get_owned(user_id, session_id)
        self.db.delete(session)
        self.db.commit()


class ChatService:
    """AI 채팅 응답 생성, 메시지 저장, 토큰 차감 흐름을 조합한다."""

    def __init__(self, db: Session):
        self.db = db
        self.session_service = ChatSessionService(db)

    def list_models(self) -> list[str]:
        """설정된 AI provider에서 사용 가능한 모델 ID 목록을 조회한다."""

        try:
            return [m.id for m in _openai_client().models.list().data]
        except APIStatusError as exc:
            raise _ai_provider_status_error(exc) from exc
        except OpenAIError as exc:
            raise AiProviderError from exc

    def send_message(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        message: str,
        model_id: str | None = None,
    ) -> tuple[Message, Message, float, bool, str | None]:
        """사용자/AI 메시지를 저장하고 탄소 토큰 차감까지 하나의 트랜잭션으로 처리한다."""

        chat_model = resolve_chat_model(model_id)
        session = self.session_service.get_owned(user_id, session_id)
        token_service = TokenService(self.db)
        state = token_service.get_or_create_today_state(user_id)
        token_service.ensure_chat_tokens_available(state)

        user_message = Message(
            user_id=user_id,
            session_id=session.id,
            role="user",
            content=message,
        )
        self.db.add(user_message)
        self.db.flush()

        try:
            response_text, carbon_gco2eq = generate_ai_response(
                self.db,
                session_id=session.id,
                message=message,
                model_id=chat_model,
            )
        except AiProviderError:
            self.db.rollback()
            raise

        response_message = Message(
            user_id=user_id,
            session_id=session.id,
            role="assistant",
            content=response_text,
            carbon_gco2eq=carbon_gco2eq,
            model_id=chat_model,
        )
        self.db.add(response_message)
        self.db.flush()

        exhausted = token_service.deduct_chat_usage(
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
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(response_message)
        return user_message, response_message, tokens_remaining, exhausted, session_title

    def list_messages(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Message], str | None]:
        """사용자가 소유한 채팅 세션의 메시지를 cursor 기반으로 조회한다."""

        session = self.session_service.get_owned(user_id, session_id)
        cursor_datetime = parse_cursor(cursor)

        query = select(Message).where(Message.session_id == session.id)
        if cursor_datetime is not None:
            query = query.where(Message.created_at < cursor_datetime)

        rows = list(self.db.scalars(query.order_by(Message.created_at.desc()).limit(limit + 1)))
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = rows[-1].created_at.isoformat()

        return list(reversed(rows)), next_cursor
