"""Tests for challenge core endpoints."""

from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import ACCESS_TOKEN_COOKIE_NAME
from app.db import Base, get_db
from app.main import app
from app.models import Challenge, DailyTokenState, User, UserProfile
from app.services.auth import create_access_token
from app.services.daily_reset import today_kst


@pytest.fixture(autouse=True)
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict[str, str]:
    return {"Cookie": f"{ACCESS_TOKEN_COOKIE_NAME}={create_access_token(user.id)}"}


def create_user(
    db_session: Session,
    *,
    email: str = "user@example.com",
) -> User:
    user = User(email=email, password_hash="hashed")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_daily_state(
    db_session: Session,
    user: User,
    *,
    tokens_remaining: float,
    challenge_count: int = 0,
) -> DailyTokenState:
    state = DailyTokenState(
        user_id=user.id,
        date=today_kst(),
        tokens_remaining=tokens_remaining,
        challenge_count=challenge_count,
    )
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


def create_challenge(
    db_session: Session,
    user: User,
    *,
    status: str,
) -> Challenge:
    challenge = Challenge(
        user_id=user.id,
        category="energy",
        title=f"{status} challenge",
        description="test challenge",
        difficulty=1,
        status=status,
    )
    db_session.add(challenge)
    db_session.commit()
    db_session.refresh(challenge)
    return challenge


def test_challenges_require_authentication(client: TestClient) -> None:
    response = client.get("/api/challenges/current")

    assert response.status_code == 401


def test_current_returns_null_when_no_open_challenge(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.get("/api/challenges/current", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["data"] == {"challenge": None}


@pytest.mark.parametrize("status", ["pending_acceptance", "active"])
def test_current_returns_open_challenge(
    client: TestClient,
    db_session: Session,
    status: str,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user, status=status)

    response = client.get("/api/challenges/current", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["challenge"]["id"] == str(challenge.id)
    assert data["challenge"]["status"] == status


def test_current_excludes_completed_challenge(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    create_challenge(db_session, user, status="completed")

    response = client.get("/api/challenges/current", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["data"] == {"challenge": None}


def test_generate_creates_pending_challenge_when_tokens_exhausted(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    db_session.add(
        UserProfile(
            user_id=user.id,
            transport_mode="car",
            diet_type="omnivore",
            housing_type="apartment",
        )
    )
    create_daily_state(db_session, user, tokens_remaining=0.0)

    response = client.post("/api/challenges/generate", headers=auth_headers(user))

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["created"] is True
    assert data["challenge"]["status"] == "pending_acceptance"
    assert data["challenge"]["category"] == "transport"

    challenge = db_session.scalar(select(Challenge))
    assert challenge is not None
    assert challenge.status == "pending_acceptance"

    state = db_session.get(DailyTokenState, {"user_id": user.id, "date": today_kst()})
    assert state is not None
    assert state.challenge_count == 1


def test_generate_rejects_when_tokens_remain(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    create_daily_state(db_session, user, tokens_remaining=1.0)

    response = client.post("/api/challenges/generate", headers=auth_headers(user))

    assert response.status_code == 409
    assert db_session.scalars(select(Challenge)).all() == []


def test_generate_returns_existing_open_challenge_without_creating_new_row(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    existing = create_challenge(db_session, user, status="active")
    create_daily_state(db_session, user, tokens_remaining=0.0)

    response = client.post("/api/challenges/generate", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["created"] is False
    assert data["challenge"]["id"] == str(existing.id)
    assert len(db_session.scalars(select(Challenge)).all()) == 1


def test_generate_rejects_when_daily_challenge_limit_reached(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    create_daily_state(db_session, user, tokens_remaining=0.0, challenge_count=3)

    response = client.post("/api/challenges/generate", headers=auth_headers(user))

    assert response.status_code == 429
    assert db_session.scalars(select(Challenge)).all() == []


def test_accept_changes_pending_challenge_to_active(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user, status="pending_acceptance")

    response = client.post(
        f"/api/challenges/{challenge.id}/accept",
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["data"]["challenge"]["status"] == "active"
    db_session.refresh(challenge)
    assert challenge.status == "active"


def test_accept_other_users_challenge_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    other_user = create_user(db_session, email="other@example.com")
    challenge = create_challenge(db_session, other_user, status="pending_acceptance")

    response = client.post(
        f"/api/challenges/{challenge.id}/accept",
        headers=auth_headers(user),
    )

    assert response.status_code == 404


@pytest.mark.parametrize("status", ["active", "completed"])
def test_accept_non_pending_challenge_returns_409(
    client: TestClient,
    db_session: Session,
    status: str,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user, status=status)

    response = client.post(
        f"/api/challenges/{challenge.id}/accept",
        headers=auth_headers(user),
    )

    assert response.status_code == 409


def test_accept_missing_challenge_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.post(
        f"/api/challenges/{uuid4()}/accept",
        headers=auth_headers(user),
    )

    assert response.status_code == 404
