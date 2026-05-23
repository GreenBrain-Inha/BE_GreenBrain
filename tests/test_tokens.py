"""Tests for token state endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTokenState
from app.services.token_service import today_kst
from tests.conftest import auth_headers, create_user


EXPECTED_FIELDS = {
    "date",
    "tokens_remaining",
    "upload_reward_given",
    "like_reward_given",
    "total_reward_given",
    "challenge_count",
    "updated_at",
}


def test_get_today_token_state_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/tokens/today")

    assert response.status_code == 401


def test_get_today_token_state_creates_default_row(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.get("/api/tokens/today", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == EXPECTED_FIELDS
    assert data["date"] == today_kst().isoformat()
    assert data["tokens_remaining"] == 150.0
    assert data["upload_reward_given"] == 0.0
    assert data["like_reward_given"] == 0.0
    assert data["total_reward_given"] == 0.0
    assert data["challenge_count"] == 0
    assert data["updated_at"] is not None

    state = db_session.scalar(select(DailyTokenState))
    assert state is not None
    assert state.user_id == user.id
    assert state.date == today_kst()


def test_get_today_token_state_returns_existing_row(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    state = DailyTokenState(
        user_id=user.id,
        date=today_kst(),
        tokens_remaining=42.5,
        upload_reward_given=20.0,
        like_reward_given=40.0,
        total_reward_given=60.0,
        challenge_count=2,
        updated_at=datetime(2026, 5, 18, 1, 2, 3, tzinfo=timezone.utc),
    )
    db_session.add(state)
    db_session.commit()

    response = client.get("/api/tokens/today", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == EXPECTED_FIELDS
    assert data["date"] == today_kst().isoformat()
    assert data["tokens_remaining"] == 42.5
    assert data["upload_reward_given"] == 20.0
    assert data["like_reward_given"] == 40.0
    assert data["total_reward_given"] == 60.0
    assert data["challenge_count"] == 2

    states = db_session.scalars(select(DailyTokenState)).all()
    assert len(states) == 1
