"""Tests for chat message send and list endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIStatusError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTokenState, Message, TokenTransaction
from app.services import chat as chat_service
from app.services.token_service import today_kst
from tests.conftest import auth_headers, create_chat_session, create_user


def runyour_status_error(status_code: int, body: object) -> APIStatusError:
    request = httpx.Request("POST", "https://api.runyour.ai/v1/chat/completions")
    response = httpx.Response(status_code, request=request, json=body)
    return APIStatusError("RunYourAI request failed", response=response, body=body)


def test_send_message_stores_messages_deducts_tokens_sets_title(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)

    monkeypatch.setattr(
        chat_service,
        "generate_ai_response",
        lambda db, *, session_id, message, model_id: ("AI 답변", 0.5),
    )
    monkeypatch.setattr(chat_service, "_generate_title", lambda message: "테스트 제목")

    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": "안녕"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["response"] == "AI 답변"
    assert body["carbon_gco2eq"] == 0.5
    assert body["tokens_remaining"] == 149.5
    assert body["exhausted"] is False
    assert body["session_title"] == "테스트 제목"
    assert body["model_id"] == chat_service.DEFAULT_CHAT_MODEL
    assert UUID(body["message_id"])
    assert UUID(body["response_message_id"])

    state = db_session.get(DailyTokenState, {"user_id": user.id, "date": today_kst()})
    assert state is not None
    assert state.tokens_remaining == 149.5

    transaction = db_session.scalar(select(TokenTransaction))
    assert transaction is not None
    assert transaction.type == "chat_usage"
    assert transaction.amount == -0.5

    assistant_message = db_session.get(Message, UUID(body["response_message_id"]))
    assert assistant_message is not None
    assert assistant_message.model_id == chat_service.DEFAULT_CHAT_MODEL



def test_send_message_uses_requested_supported_model(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)
    seen_model_id = None

    def fake_generate_ai_response(
        db: Session,
        *,
        session_id: UUID,
        message: str,
        model_id: str,
    ) -> tuple[str, float]:
        nonlocal seen_model_id
        seen_model_id = model_id
        return "Claude 답변", 0.25

    monkeypatch.setattr(chat_service, "generate_ai_response", fake_generate_ai_response)
    monkeypatch.setattr(chat_service, "_generate_title", lambda message: "모델 테스트")

    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": "모델 선택", "model_id": "anthropic/claude-sonnet-4-6"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["model_id"] == "anthropic/claude-sonnet-4-6"
    assert seen_model_id == "anthropic/claude-sonnet-4-6"

    assistant_message = db_session.get(Message, UUID(body["response_message_id"]))
    assert assistant_message is not None
    assert assistant_message.model_id == "anthropic/claude-sonnet-4-6"


def test_send_message_rejects_unsupported_model_before_ai_call(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)

    def fail(*args: object, **kwargs: object) -> tuple[str, float]:
        raise AssertionError("AI should not be called for unsupported models")

    monkeypatch.setattr(chat_service, "generate_ai_response", fail)

    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": "모델 선택", "model_id": "unknown/some-model"},
        headers=auth_headers(user),
    )

    assert response.status_code == 400
    assert response.json()["message"] == "지원하지 않는 채팅 모델입니다."
    assert db_session.scalars(select(Message)).all() == []



def test_send_message_title_not_set_on_subsequent_messages(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)
    session.title = "기존 제목"
    db_session.commit()

    monkeypatch.setattr(
        chat_service,
        "generate_ai_response",
        lambda db, *, session_id, message, model_id: ("응답", 0.1),
    )

    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": "두 번째 메시지"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["data"]["session_title"] is None


def test_send_message_title_falls_back_to_first_30_chars_when_ai_fails(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)

    monkeypatch.setattr(
        chat_service,
        "generate_ai_response",
        lambda db, *, session_id, message, model_id: ("응답", None),
    )
    monkeypatch.setattr(chat_service, "_generate_title", lambda message: None)

    long_message = "가" * 50
    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": long_message},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["data"]["session_title"] == "가" * 30


def test_send_message_returns_403_when_tokens_exhausted(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)
    db_session.add(DailyTokenState(user_id=user.id, date=today_kst(), tokens_remaining=0.0))
    db_session.commit()

    def fail(*args, **kwargs):
        raise AssertionError("AI should not be called when tokens are exhausted")

    monkeypatch.setattr(chat_service, "generate_ai_response", fail)

    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": "차단"},
        headers=auth_headers(user),
    )

    assert response.status_code == 403


def test_send_message_returns_502_when_ai_fails(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)

    def raise_ai_error(*args: object, **kwargs: object) -> tuple[str, float]:
        raise chat_service.AiProviderError

    monkeypatch.setattr(chat_service, "generate_ai_response", raise_ai_error)

    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": "AI 실패"},
        headers=auth_headers(user),
    )

    assert response.status_code == 502


def test_send_message_surfaces_runyour_api_status_error(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)

    class FakeCompletions:
        def create(self, **kwargs: object) -> object:
            raise runyour_status_error(
                429,
                {"error": {"message": "model quota exceeded", "code": "rate_limit"}},
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(chat_service, "_openai_client", lambda: FakeClient())

    response = client.post(
        f"/api/chat/sessions/{session.id}/messages",
        json={"message": "AI 실패"},
        headers=auth_headers(user),
    )

    assert response.status_code == 429
    body = response.json()
    assert body["message"] == "AI 제공자 오류(429): model quota exceeded"
    assert db_session.scalars(select(Message)).all() == []


def test_send_message_returns_404_for_other_users_session(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    other_user = create_user(db_session, email="other@example.com")
    other_session = create_chat_session(db_session, other_user)

    response = client.post(
        f"/api/chat/sessions/{other_session.id}/messages",
        json={"message": "탈취"},
        headers=auth_headers(user),
    )

    assert response.status_code == 404


def test_list_messages_uses_cursor_pagination(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)

    for i in range(3):
        db_session.add(
            Message(
                user_id=user.id,
                session_id=session.id,
                role="user",
                content=f"message-{i}",
                model_id="openai/gpt-5.2",
                created_at=datetime(2026, 5, 14, 0, i, tzinfo=timezone.utc),
            )
        )
    db_session.commit()

    first_response = client.get(
        f"/api/chat/sessions/{session.id}/messages?limit=2",
        headers=auth_headers(user),
    )
    assert first_response.status_code == 200
    first_body = first_response.json()["data"]
    assert [m["content"] for m in first_body["items"]] == ["message-1", "message-2"]
    assert [m["model_id"] for m in first_body["items"]] == ["openai/gpt-5.2", "openai/gpt-5.2"]
    assert first_body["next_cursor"]

    second_response = client.get(
        f"/api/chat/sessions/{session.id}/messages?limit=2&cursor={first_body['next_cursor']}",
        headers=auth_headers(user),
    )
    assert second_response.status_code == 200
    second_body = second_response.json()["data"]
    assert [m["content"] for m in second_body["items"]] == ["message-0"]
    assert second_body["next_cursor"] is None


def test_list_messages_returns_404_for_other_users_session(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    other_user = create_user(db_session, email="other@example.com")
    other_session = create_chat_session(db_session, other_user)

    response = client.get(
        f"/api/chat/sessions/{other_session.id}/messages",
        headers=auth_headers(user),
    )

    assert response.status_code == 404


def test_chat_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/chat/sessions/{uuid4()}/messages")

    assert response.status_code == 401
