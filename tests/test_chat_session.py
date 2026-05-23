"""Tests for chat session CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, create_chat_session, create_user


def test_create_session_returns_201_with_null_title(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    response = client.post("/api/chat/sessions", headers=auth_headers(user))

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["title"] is None
    assert UUID(body["id"])


def test_list_sessions_returns_own_sessions_only(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    other_user = create_user(db_session, email="other@example.com")
    create_chat_session(db_session, user)
    create_chat_session(db_session, other_user)

    response = client.get("/api/chat/sessions", headers=auth_headers(user))

    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body["items"]) == 1
    assert body["next_cursor"] is None


def test_update_session_title(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    session = create_chat_session(db_session, user)

    response = client.patch(
        f"/api/chat/sessions/{session.id}",
        json={"title": "새 제목"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "새 제목"


def test_update_session_returns_404_for_other_users_session(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    other_user = create_user(db_session, email="other@example.com")
    other_session = create_chat_session(db_session, other_user)

    response = client.patch(
        f"/api/chat/sessions/{other_session.id}",
        json={"title": "탈취 시도"},
        headers=auth_headers(user),
    )

    assert response.status_code == 404


def test_delete_session_removes_session_and_messages(
    client: TestClient, db_session: Session
) -> None:
    from sqlalchemy import select
    from app.models import ChatSession, Message

    user = create_user(db_session)
    session = create_chat_session(db_session, user)
    db_session.add(
        Message(user_id=user.id, session_id=session.id, role="user", content="삭제될 메시지")
    )
    db_session.commit()

    response = client.delete(f"/api/chat/sessions/{session.id}", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert db_session.get(ChatSession, session.id) is None
    assert db_session.scalars(select(Message)).all() == []


def test_delete_session_returns_404_for_other_users_session(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    other_user = create_user(db_session, email="other@example.com")
    other_session = create_chat_session(db_session, other_user)

    response = client.delete(
        f"/api/chat/sessions/{other_session.id}", headers=auth_headers(user)
    )

    assert response.status_code == 404
