"""Tests for challenge photo like endpoint."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Challenge, ChallengePhoto, Like, User
from app.services.storage import get_file_storage
from tests.conftest import auth_headers, create_user


class FakeStorage:
    def get_url(self, key: str) -> str:
        return f"/files/{key}"


@pytest.fixture
def storage_override() -> Generator[None, None, None]:
    def override_get_file_storage() -> FakeStorage:
        return FakeStorage()

    app.dependency_overrides[get_file_storage] = override_get_file_storage
    yield
    app.dependency_overrides.pop(get_file_storage, None)


def create_challenge_photo(
    db_session: Session,
    user: User,
    *,
    title: str = "Proof challenge",
    file_path: str = "proof.webp",
    created_at: datetime | None = None,
) -> ChallengePhoto:
    timestamp = created_at or datetime(2026, 5, 19, 9, 0, tzinfo=timezone.utc)
    challenge = Challenge(
        user_id=user.id,
        category="energy",
        title=title,
        description=f"{title} description",
        difficulty=2,
        status="completed",
        completed_at=timestamp,
    )
    db_session.add(challenge)
    db_session.flush()

    photo = ChallengePhoto(
        challenge_id=challenge.id,
        user_id=user.id,
        file_path=file_path,
        upload_rewarded=True,
        created_at=timestamp,
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)
    return photo


def test_like_challenge_photo_creates_like_and_returns_count(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="uploader@example.com")
    liker = create_user(db_session, email="liker@example.com")
    other_liker = create_user(db_session, email="other-liker@example.com")
    photo = create_challenge_photo(db_session, uploader)
    db_session.add(Like(photo_id=photo.id, liker_user_id=other_liker.id))
    db_session.commit()

    response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "photo_id": str(photo.id),
        "liked": True,
        "like_count": 2,
        "reward_given": False,
        "reward_amount": 0.0,
        "tokens_remaining": None,
    }
    like = db_session.scalar(
        select(Like).where(Like.photo_id == photo.id, Like.liker_user_id == liker.id)
    )
    assert like is not None


def test_like_challenge_photo_updates_feed_like_count_and_liked_by_me(
    client: TestClient,
    db_session: Session,
    storage_override: None,
) -> None:
    uploader = create_user(db_session, email="feed-uploader@example.com")
    liker = create_user(db_session, email="feed-liker@example.com")
    photo = create_challenge_photo(db_session, uploader, file_path="feed-proof.webp")

    like_response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker),
    )
    assert like_response.status_code == 200

    feed_response = client.get("/api/challenges/feed", headers=auth_headers(liker))

    assert feed_response.status_code == 200
    data = feed_response.json()["data"]
    assert data["items"][0]["photo_id"] == str(photo.id)
    assert data["items"][0]["like_count"] == 1
    assert data["items"][0]["liked_by_me"] is True


def test_like_challenge_photo_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="auth-uploader@example.com")
    photo = create_challenge_photo(db_session, uploader)

    response = client.post(f"/api/challenge-photos/{photo.id}/like")

    assert response.status_code == 401


def test_like_challenge_photo_returns_404_for_missing_photo(
    client: TestClient,
    db_session: Session,
) -> None:
    liker = create_user(db_session, email="missing-liker@example.com")

    response = client.post(
        f"/api/challenge-photos/{uuid4()}/like",
        headers=auth_headers(liker),
    )

    assert response.status_code == 404


def test_like_challenge_photo_rejects_own_photo(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="own-uploader@example.com")
    photo = create_challenge_photo(db_session, uploader)

    response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(uploader),
    )

    assert response.status_code == 403
    assert db_session.scalars(select(Like)).all() == []


def test_like_challenge_photo_rejects_duplicate_like(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="duplicate-uploader@example.com")
    liker = create_user(db_session, email="duplicate-liker@example.com")
    photo = create_challenge_photo(db_session, uploader)
    db_session.add(Like(photo_id=photo.id, liker_user_id=liker.id))
    db_session.commit()

    response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker),
    )

    assert response.status_code == 409
    likes = db_session.scalars(select(Like).where(Like.photo_id == photo.id)).all()
    assert len(likes) == 1
