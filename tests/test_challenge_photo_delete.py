"""Tests for challenge photo delete endpoint."""

from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Challenge, ChallengePhoto, DailyTokenState, Like, TokenTransaction, User
from app.services.storage import StorageWriteError, get_file_storage
from app.services.token_service import today_kst
from tests.conftest import auth_headers, create_user


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def put(self, key: str, data: bytes, content_type: str) -> str:
        del data, content_type
        return key

    def get_url(self, key: str) -> str:
        return f"/files/{key}"

    def delete(self, key: str) -> None:
        self.deleted.append(key)


class FailingDeleteStorage(FakeStorage):
    def delete(self, key: str) -> None:
        self.deleted.append(key)
        raise StorageWriteError


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def storage_override(storage: FakeStorage) -> Generator[FakeStorage, None, None]:
    def override_get_file_storage() -> FakeStorage:
        return storage

    app.dependency_overrides[get_file_storage] = override_get_file_storage
    yield storage
    app.dependency_overrides.pop(get_file_storage, None)


def create_challenge_photo(
    db_session: Session,
    user: User,
    *,
    file_path: str = "challenge-photos/delete-target.webp",
) -> ChallengePhoto:
    challenge = Challenge(
        user_id=user.id,
        category="energy",
        title="Delete proof",
        description="Delete proof description",
        difficulty=1,
        status="completed",
    )
    db_session.add(challenge)
    db_session.flush()
    photo = ChallengePhoto(
        challenge_id=challenge.id,
        user_id=user.id,
        file_path=file_path,
        upload_rewarded=True,
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)
    return photo


def create_daily_state(db_session: Session, user: User) -> DailyTokenState:
    state = DailyTokenState(
        user_id=user.id,
        date=today_kst(),
        tokens_remaining=150.0,
    )
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


def create_token_transaction(
    db_session: Session,
    *,
    user: User,
    photo: ChallengePhoto,
) -> TokenTransaction:
    state = create_daily_state(db_session, user)
    transaction = TokenTransaction(
        user_id=user.id,
        daily_state_date=state.date,
        type="upload_reward",
        amount=20.0,
        balance_after=170.0,
        source_type="photo",
        source_id=photo.id,
        memo="upload reward",
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction


def test_delete_challenge_photo_deletes_owner_photo_storage_likes_but_keeps_transactions(
    client: TestClient,
    db_session: Session,
    storage_override: FakeStorage,
) -> None:
    owner = create_user(db_session, email="delete-owner@example.com")
    liker = create_user(db_session, email="delete-liker@example.com")
    photo = create_challenge_photo(db_session, owner)
    db_session.add(Like(photo_id=photo.id, liker_user_id=liker.id))
    db_session.commit()
    transaction = create_token_transaction(db_session, user=owner, photo=photo)

    response = client.delete(
        f"/api/challenge-photos/{photo.id}",
        headers=auth_headers(owner),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] is None
    assert storage_override.deleted == [photo.file_path]
    assert db_session.get(ChallengePhoto, photo.id) is None
    assert db_session.scalars(select(Like).where(Like.photo_id == photo.id)).all() == []
    assert db_session.get(TokenTransaction, transaction.id) is not None

    feed_response = client.get("/api/challenges/feed", headers=auth_headers(owner))
    assert feed_response.status_code == 200
    assert feed_response.json()["data"]["items"] == []

    liked_users_response = client.get(
        f"/api/challenge-photos/{photo.id}/likes",
        headers=auth_headers(owner),
    )
    assert liked_users_response.status_code == 404


def test_delete_challenge_photo_rejects_other_user(
    client: TestClient,
    db_session: Session,
    storage_override: FakeStorage,
) -> None:
    owner = create_user(db_session, email="forbidden-owner@example.com")
    other = create_user(db_session, email="forbidden-other@example.com")
    photo = create_challenge_photo(db_session, owner)

    response = client.delete(
        f"/api/challenge-photos/{photo.id}",
        headers=auth_headers(other),
    )

    assert response.status_code == 403
    assert storage_override.deleted == []
    assert db_session.get(ChallengePhoto, photo.id) is not None


def test_delete_challenge_photo_returns_404_for_missing_photo(
    client: TestClient,
    db_session: Session,
    storage_override: FakeStorage,
) -> None:
    user = create_user(db_session, email="missing-delete@example.com")

    response = client.delete(
        f"/api/challenge-photos/{uuid4()}",
        headers=auth_headers(user),
    )

    assert response.status_code == 404
    assert storage_override.deleted == []


def test_delete_challenge_photo_requires_authentication(
    client: TestClient,
    db_session: Session,
    storage_override: FakeStorage,
) -> None:
    owner = create_user(db_session, email="auth-delete-owner@example.com")
    photo = create_challenge_photo(db_session, owner)

    response = client.delete(f"/api/challenge-photos/{photo.id}")

    assert response.status_code == 401
    assert storage_override.deleted == []
    assert db_session.get(ChallengePhoto, photo.id) is not None


def test_delete_challenge_photo_returns_502_when_storage_delete_fails(
    client: TestClient,
    db_session: Session,
) -> None:
    storage = FailingDeleteStorage()

    def override_get_file_storage() -> FailingDeleteStorage:
        return storage

    app.dependency_overrides[get_file_storage] = override_get_file_storage
    owner = create_user(db_session, email="storage-fail-owner@example.com")
    photo = create_challenge_photo(db_session, owner)
    try:
        response = client.delete(
            f"/api/challenge-photos/{photo.id}",
            headers=auth_headers(owner),
        )
    finally:
        app.dependency_overrides.pop(get_file_storage, None)

    assert response.status_code == 502
    assert storage.deleted == [photo.file_path]
    assert db_session.get(ChallengePhoto, photo.id) is not None
