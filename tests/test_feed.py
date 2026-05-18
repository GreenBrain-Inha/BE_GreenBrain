"""Tests for challenge proof feed endpoint."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Challenge, ChallengePhoto, Like, User
from app.services.storage import get_file_storage
from tests.conftest import auth_headers, create_user


class FakeStorage:
    def get_url(self, key: str) -> str:
        return f"/files/{key}"


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

    def override_get_file_storage() -> FakeStorage:
        return FakeStorage()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_file_storage] = override_get_file_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_challenge_with_photo(
    db_session: Session,
    user: User,
    *,
    title: str,
    file_path: str,
    created_at: datetime,
) -> ChallengePhoto:
    challenge = Challenge(
        user_id=user.id,
        category="energy",
        title=title,
        description=f"{title} description",
        difficulty=2,
        status="completed",
        completed_at=created_at,
    )
    db_session.add(challenge)
    db_session.flush()
    photo = ChallengePhoto(
        challenge_id=challenge.id,
        user_id=user.id,
        file_path=file_path,
        upload_rewarded=True,
        created_at=created_at,
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)
    return photo


def test_challenge_feed_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/challenges/feed")

    assert response.status_code == 401
    assert response.json() == {"message": "Not authenticated"}


def test_challenge_feed_returns_items_latest_first_with_like_counts(
    client: TestClient,
    db_session: Session,
) -> None:
    viewer = create_user(db_session, email="viewer@example.com")
    older_uploader = create_user(db_session, email="older-uploader@example.com")
    older_uploader.nickname = "Older Uploader"
    older_uploader.profile_image_url = "/profiles/older-uploader.png"
    newer_uploader = create_user(db_session, email="newer-uploader@example.com")
    newer_uploader.nickname = "Newer Uploader"
    newer_uploader.profile_image_url = "/profiles/newer-uploader.png"
    liker_1 = create_user(db_session, email="liker1@example.com")
    liker_2 = create_user(db_session, email="liker2@example.com")
    db_session.commit()

    older_photo = create_challenge_with_photo(
        db_session,
        older_uploader,
        title="Older proof",
        file_path="older.webp",
        created_at=datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc),
    )
    newer_photo = create_challenge_with_photo(
        db_session,
        newer_uploader,
        title="Newer proof",
        file_path="newer.webp",
        created_at=datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc),
    )
    db_session.add_all(
        [
            Like(photo_id=newer_photo.id, liker_user_id=liker_1.id),
            Like(photo_id=newer_photo.id, liker_user_id=liker_2.id),
            Like(photo_id=older_photo.id, liker_user_id=liker_1.id),
        ]
    )
    db_session.commit()

    response = client.get("/api/challenges/feed", headers=auth_headers(viewer))

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert [item["photo"]["id"] for item in body["items"]] == [
        str(newer_photo.id),
        str(older_photo.id),
    ]

    first = body["items"][0]
    assert set(first) == {"photo", "challenge", "user", "like_count"}
    assert first["photo"]["challenge_id"] == str(newer_photo.challenge_id)
    assert first["photo"]["file_url"] == "/files/newer.webp"
    assert first["photo"]["created_at"] is not None
    assert first["challenge"] == {
        "id": str(newer_photo.challenge_id),
        "title": "Newer proof",
        "description": "Newer proof description",
        "category": "energy",
        "difficulty": 2,
    }
    assert first["user"] == {
        "id": str(newer_uploader.id),
        "nickname": "Newer Uploader",
        "profile_image_url": "/profiles/newer-uploader.png",
    }
    assert first["like_count"] == 2
    assert body["items"][1]["like_count"] == 1
    assert "older-uploader@example.com" not in response.text
    assert "newer-uploader@example.com" not in response.text
