"""Tests for challenge photo liked users endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Challenge, ChallengePhoto, Like, User
from tests.conftest import auth_headers, create_user


def create_challenge_photo(
    db_session: Session,
    user: User,
    *,
    created_at: datetime | None = None,
) -> ChallengePhoto:
    timestamp = created_at or datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc)
    challenge = Challenge(
        user_id=user.id,
        category="energy",
        title="Proof challenge",
        description="Proof challenge description",
        difficulty=2,
        status="completed",
        completed_at=timestamp,
    )
    db_session.add(challenge)
    db_session.flush()

    photo = ChallengePhoto(
        challenge_id=challenge.id,
        user_id=user.id,
        file_path="proof.webp",
        upload_rewarded=True,
        created_at=timestamp,
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)
    return photo


def add_like(
    db_session: Session,
    *,
    photo: ChallengePhoto,
    user: User,
    created_at: datetime,
) -> Like:
    like = Like(
        photo_id=photo.id,
        liker_user_id=user.id,
        created_at=created_at,
    )
    db_session.add(like)
    db_session.commit()
    db_session.refresh(like)
    return like


def test_liked_users_returns_latest_first_with_user_profile_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    viewer = create_user(db_session, email="viewer@example.com")
    uploader = create_user(db_session, email="uploader@example.com")
    older_liker = create_user(db_session, email="older-liker@example.com")
    newer_liker = create_user(db_session, email="newer-liker@example.com")
    newest_liker = create_user(db_session, email="newest-liker@example.com")
    older_liker.nickname = "Older Liker"
    older_liker.profile_image_url = "/profiles/older.png"
    newer_liker.nickname = "Newer Liker"
    newer_liker.profile_image_url = "/profiles/newer.png"
    newest_liker.nickname = "Newest Liker"
    newest_liker.profile_image_url = "/profiles/newest.png"
    db_session.commit()
    photo = create_challenge_photo(db_session, uploader)

    add_like(
        db_session,
        photo=photo,
        user=older_liker,
        created_at=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc),
    )
    add_like(
        db_session,
        photo=photo,
        user=newer_liker,
        created_at=datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc),
    )
    add_like(
        db_session,
        photo=photo,
        user=newest_liker,
        created_at=datetime(2026, 5, 24, 11, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        f"/api/challenge-photos/{photo.id}/likes",
        headers=auth_headers(viewer),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "좋아요 사용자 목록 조회 성공"
    data = body["data"]
    assert data["total"] == 3
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert [item["user_id"] for item in data["items"]] == [
        str(newest_liker.id),
        str(newer_liker.id),
        str(older_liker.id),
    ]

    first = data["items"][0]
    assert set(first) == {"user_id", "nickname", "profile_image_url", "liked_at"}
    assert first["nickname"] == "Newest Liker"
    assert first["profile_image_url"] == "/profiles/newest.png"
    assert first["liked_at"] is not None
    assert "newest-liker@example.com" not in response.text


def test_liked_users_applies_limit_and_offset(
    client: TestClient,
    db_session: Session,
) -> None:
    viewer = create_user(db_session, email="page-viewer@example.com")
    uploader = create_user(db_session, email="page-uploader@example.com")
    first_liker = create_user(db_session, email="page-first@example.com")
    second_liker = create_user(db_session, email="page-second@example.com")
    third_liker = create_user(db_session, email="page-third@example.com")
    photo = create_challenge_photo(db_session, uploader)

    add_like(
        db_session,
        photo=photo,
        user=first_liker,
        created_at=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc),
    )
    add_like(
        db_session,
        photo=photo,
        user=second_liker,
        created_at=datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc),
    )
    add_like(
        db_session,
        photo=photo,
        user=third_liker,
        created_at=datetime(2026, 5, 24, 11, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        f"/api/challenge-photos/{photo.id}/likes?limit=1&offset=1",
        headers=auth_headers(viewer),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["user_id"] == str(second_liker.id)


def test_liked_users_returns_404_for_missing_photo(
    client: TestClient,
    db_session: Session,
) -> None:
    viewer = create_user(db_session, email="missing-viewer@example.com")

    response = client.get(
        f"/api/challenge-photos/{uuid4()}/likes",
        headers=auth_headers(viewer),
    )

    assert response.status_code == 404


def test_liked_users_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/challenge-photos/{uuid4()}/likes")

    assert response.status_code == 401
