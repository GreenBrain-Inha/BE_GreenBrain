"""Tests for token state endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import pytest

from app.models import DailyTokenState
from app.services.token_service import today_kst, mgco2_from_carbon
from tests.conftest import auth_headers, create_user


@pytest.mark.parametrize(
    "carbon_gco2eq, expected",
    [
        (None, None),     # 탄소 미지원 모델
        (0.0, 1),         # 최소 1
        (0.0003, 1),      # 올림 후 최소 1 (ceil(0.3) = 1)
        (0.25, 250),      # gCO₂eq → mgCO₂eq (0.25g = 250mg)
        (2.321, 2321),    # 올림 (gemini 예시)
    ],
)
def test_mgco2_from_carbon(carbon_gco2eq: float | None, expected: int | None) -> None:
    assert mgco2_from_carbon(carbon_gco2eq) == expected


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
    assert data["tokens_remaining"] == 10_000
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
        tokens_remaining=42,
        upload_reward_given=20,
        like_reward_given=40,
        total_reward_given=60,
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
    assert data["tokens_remaining"] == 42
    assert data["upload_reward_given"] == 20
    assert data["like_reward_given"] == 40
    assert data["total_reward_given"] == 60
    assert data["challenge_count"] == 2

    states = db_session.scalars(select(DailyTokenState)).all()
    assert len(states) == 1
