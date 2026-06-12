"""Tests for challenge photo upload endpoint."""

from __future__ import annotations

from collections.abc import Generator
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import ACCESS_TOKEN_COOKIE_NAME
from app.db import Base, get_db
from app.main import app
from app.models import Challenge, ChallengePhoto, DailyTokenState, TokenTransaction, User
from app.services.auth_service import create_access_token
from app.services.token_service import today_kst
from app.services.storage import StorageWriteError, get_file_storage


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put(self, key: str, data: bytes, content_type: str) -> str:
        del content_type
        self.files[key] = data
        return key

    def get_url(self, key: str) -> str:
        return f"/files/{key}"

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.files.pop(key, None)


class FailingStorage(FakeStorage):
    def put(self, key: str, data: bytes, content_type: str) -> str:
        raise StorageWriteError


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
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client(db_session: Session, storage: FakeStorage) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_get_file_storage() -> FakeStorage:
        return storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_file_storage] = override_get_file_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict[str, str]:
    return {"Cookie": f"{ACCESS_TOKEN_COOKIE_NAME}={create_access_token(user.id)}"}


def create_user(db_session: Session, *, email: str = "user@example.com") -> User:
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
) -> DailyTokenState:
    state = DailyTokenState(
        user_id=user.id,
        date=today_kst(),
        tokens_remaining=tokens_remaining,
    )
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


def create_challenge(db_session: Session, user: User, *, status: str = "active") -> Challenge:
    challenge = Challenge(
        user_id=user.id,
        category="energy",
        title="Upload proof",
        description="Upload a challenge photo.",
        difficulty=1,
        status=status,
    )
    db_session.add(challenge)
    db_session.commit()
    db_session.refresh(challenge)
    return challenge


def image_upload(*, content_type: str = "image/png", image_format: str = "PNG") -> dict[str, tuple[str, bytes, str]]:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color="green").save(buffer, format=image_format)
    return {"file": ("proof.png", buffer.getvalue(), content_type)}


def test_photo_upload_requires_authentication(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)

    response = client.post(f"/api/challenges/{challenge.id}/photo", files=image_upload())

    assert response.status_code == 401


def test_photo_upload_missing_challenge_returns_404(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.post(
        f"/api/challenges/{uuid4()}/photo",
        headers=auth_headers(user),
        files=image_upload(),
    )

    assert response.status_code == 404


def test_photo_upload_other_users_challenge_returns_403(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    other_user = create_user(db_session, email="other@example.com")
    challenge = create_challenge(db_session, other_user)

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files=image_upload(),
    )

    assert response.status_code == 403


@pytest.mark.parametrize("status", ["pending_acceptance", "completed"])
def test_photo_upload_non_active_challenge_returns_409(
    client: TestClient,
    db_session: Session,
    status: str,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user, status=status)

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files=image_upload(),
    )

    assert response.status_code == 409


def test_photo_upload_active_challenge_succeeds_and_records_reward(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)
    create_daily_state(db_session, user, tokens_remaining=10000)

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files=image_upload(),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["photo"]["challenge_id"] == str(challenge.id)
    assert data["photo"]["file_url"].startswith("/files/challenge-photos/")
    assert data["challenge"]["status"] == "completed"
    assert data["challenge"]["completed_at"] is not None
    assert data["reward"] == {
        "type": "upload_reward",
        "reward_amount": 2000,
        "tokens_remaining": 12000,
    }
    assert type(data["reward"]["reward_amount"]) is int
    assert type(data["reward"]["tokens_remaining"]) is int

    photo = db_session.scalar(select(ChallengePhoto))
    assert photo is not None
    assert photo.challenge_id == challenge.id
    assert photo.file_path.startswith("challenge-photos/")
    assert photo.upload_rewarded is True

    db_session.refresh(challenge)
    assert challenge.status == "completed"
    assert challenge.completed_at is not None

    transaction = db_session.scalar(select(TokenTransaction))
    assert transaction is not None
    assert transaction.type == "upload_reward"
    assert transaction.amount == 2000
    assert transaction.balance_after == 12000
    assert transaction.source_type == "photo"
    assert transaction.source_id == photo.id


def test_photo_upload_can_recover_tokens_above_daily_base_amount(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)
    create_daily_state(db_session, user, tokens_remaining=14000)

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files=image_upload(),
    )

    assert response.status_code == 201
    assert response.json()["data"]["reward"] == {
        "type": "upload_reward",
        "reward_amount": 2000,
        "tokens_remaining": 16000,
    }


def test_photo_upload_grants_reward_when_tokens_are_at_daily_base_amount(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)
    create_daily_state(db_session, user, tokens_remaining=15000)

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files=image_upload(),
    )

    assert response.status_code == 201
    assert response.json()["data"]["reward"] == {
        "type": "upload_reward",
        "reward_amount": 2000,
        "tokens_remaining": 17000,
    }
    assert db_session.scalar(select(ChallengePhoto)) is not None


def test_photo_upload_rejects_duplicate_photo(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)
    db_session.add(
        ChallengePhoto(
            challenge_id=challenge.id,
            user_id=user.id,
            file_path="existing.webp",
            upload_rewarded=True,
        )
    )
    db_session.commit()

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files=image_upload(),
    )

    assert response.status_code == 409


def test_photo_upload_rejects_files_larger_than_10mb(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)
    large_file = {"file": ("large.jpg", b"0" * (10 * 1024 * 1024 + 1), "image/jpeg")}

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files=large_file,
    )

    assert response.status_code == 413


def test_photo_upload_rejects_unsupported_mime_type(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files={"file": ("proof.gif", b"GIF89a", "image/gif")},
    )

    assert response.status_code == 415


def test_photo_upload_rejects_corrupt_image(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    challenge = create_challenge(db_session, user)

    response = client.post(
        f"/api/challenges/{challenge.id}/photo",
        headers=auth_headers(user),
        files={"file": ("proof.png", b"not an image", "image/png")},
    )

    assert response.status_code == 422


def test_storage_write_failure_returns_502_without_db_changes(
    db_session: Session,
) -> None:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_get_file_storage() -> FailingStorage:
        return FailingStorage()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_file_storage] = override_get_file_storage

    user = create_user(db_session)
    challenge = create_challenge(db_session, user)
    create_daily_state(db_session, user, tokens_remaining=10000)
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                f"/api/challenges/{challenge.id}/photo",
                headers=auth_headers(user),
                files=image_upload(),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert db_session.scalars(select(ChallengePhoto)).all() == []
    assert db_session.scalars(select(TokenTransaction)).all() == []
    db_session.refresh(challenge)
    assert challenge.status == "active"
