"""최소 기능 챌린지 피드 핵심 플로우 회귀 테스트."""

from __future__ import annotations

from collections.abc import Generator
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Challenge, ChallengePhoto, DailyTokenState, TokenTransaction, UserProfile
from app.services import challenge_service
from app.services.storage import get_file_storage
from app.services.token_service import today_kst
from tests.conftest import auth_headers, create_user


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> str:
        del content_type
        self.files[key] = data
        return key

    def get_url(self, key: str) -> str:
        return f"/files/{key}"

    def delete(self, key: str) -> None:
        self.files.pop(key, None)


@pytest.fixture
def storage_override() -> Generator[FakeStorage, None, None]:
    storage = FakeStorage()

    def override_get_file_storage() -> FakeStorage:
        return storage

    app.dependency_overrides[get_file_storage] = override_get_file_storage
    yield storage
    app.dependency_overrides.pop(get_file_storage, None)


def create_daily_state(
    db_session: Session,
    user_id: UUID,
    *,
    tokens_remaining: float,
) -> DailyTokenState:
    state = DailyTokenState(
        user_id=user_id,
        date=today_kst(),
        tokens_remaining=tokens_remaining,
    )
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


def create_profile(db_session: Session, user_id: UUID) -> UserProfile:
    profile = UserProfile(
        user_id=user_id,
        transport_mode="car",
        diet_type="omnivore",
        housing_type="apartment",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def image_upload() -> dict[str, tuple[str, bytes, str]]:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color="green").save(buffer, format="PNG")
    return {"file": ("proof.png", buffer.getvalue(), "image/png")}


def test_challenge_generation_upload_feed_like_and_liked_users_flow(
    client: TestClient,
    db_session: Session,
    storage_override: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploader = create_user(db_session, email="flow-uploader@example.com")
    uploader.nickname = "Uploader"
    uploader.profile_image_url = "/profiles/uploader.png"
    liker = create_user(db_session, email="flow-liker@example.com")
    liker.nickname = "Flow Liker"
    liker.profile_image_url = "/profiles/liker.png"
    db_session.commit()
    create_profile(db_session, uploader.id)
    create_daily_state(db_session, uploader.id, tokens_remaining=15000)
    monkeypatch.setattr(challenge_service.random, "choice", lambda candidates: candidates[0])

    generate_response = client.post("/api/challenges/generate", headers=auth_headers(uploader))

    assert generate_response.status_code == 201
    generated = generate_response.json()["data"]
    assert generated["created"] is True
    assert generated["challenge"]["status"] == "pending_acceptance"
    challenge_id = UUID(generated["challenge"]["id"])

    accept_response = client.post(
        f"/api/challenges/{challenge_id}/accept",
        headers=auth_headers(uploader),
    )

    assert accept_response.status_code == 200
    assert accept_response.json()["data"]["challenge"]["status"] == "active"

    upload_response = client.post(
        f"/api/challenges/{challenge_id}/photo",
        headers=auth_headers(uploader),
        files=image_upload(),
    )

    assert upload_response.status_code == 201
    uploaded = upload_response.json()["data"]
    assert uploaded["challenge"]["status"] == "completed"
    photo_id = UUID(uploaded["photo"]["id"])
    assert uploaded["photo"]["file_url"].startswith("/files/challenge-photos/")

    challenge = db_session.get(Challenge, challenge_id)
    assert challenge is not None
    assert challenge.status == "completed"
    photo = db_session.get(ChallengePhoto, photo_id)
    assert photo is not None

    feed_before_like_response = client.get(
        "/api/challenges/feed",
        headers=auth_headers(uploader),
    )

    assert feed_before_like_response.status_code == 200
    feed_before_like_text = feed_before_like_response.text
    feed_before_like = feed_before_like_response.json()["data"]
    assert feed_before_like["total"] == 1
    feed_item = feed_before_like["items"][0]
    assert set(feed_item) >= {"photo_url", "like_count", "liked_by_me"}
    assert feed_item["photo_id"] == str(photo_id)
    assert feed_item["photo_url"].startswith("/files/challenge-photos/")
    assert feed_item["like_count"] == 0
    assert feed_item["liked_by_me"] is False
    assert "flow-uploader@example.com" not in feed_before_like_text

    like_response = client.post(
        f"/api/challenge-photos/{photo_id}/like",
        headers=auth_headers(liker),
    )

    assert like_response.status_code == 200
    assert like_response.json()["data"]["like_count"] == 1

    feed_after_like_response = client.get(
        "/api/challenges/feed",
        headers=auth_headers(liker),
    )

    assert feed_after_like_response.status_code == 200
    feed_after_like = feed_after_like_response.json()["data"]
    liked_feed_item = feed_after_like["items"][0]
    assert liked_feed_item["photo_id"] == str(photo_id)
    assert liked_feed_item["like_count"] == 1
    assert liked_feed_item["liked_by_me"] is True
    assert "flow-uploader@example.com" not in feed_after_like_response.text
    assert "flow-liker@example.com" not in feed_after_like_response.text

    liked_users_response = client.get(
        f"/api/challenge-photos/{photo_id}/likes",
        headers=auth_headers(uploader),
    )

    assert liked_users_response.status_code == 200
    liked_users_text = liked_users_response.text
    liked_users = liked_users_response.json()["data"]
    assert liked_users["total"] == 1
    assert liked_users["limit"] == 20
    assert liked_users["offset"] == 0
    liked_user = liked_users["items"][0]
    assert set(liked_user) == {"user_id", "nickname", "profile_image_url", "liked_at"}
    assert liked_user["user_id"] == str(liker.id)
    assert liked_user["nickname"] == "Flow Liker"
    assert liked_user["profile_image_url"] == "/profiles/liker.png"
    assert liked_user["liked_at"] is not None
    assert "flow-liker@example.com" not in liked_users_text


def test_third_like_reward_flow_keeps_tokens_above_daily_base(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="milestone-uploader@example.com")
    liker_1 = create_user(db_session, email="milestone-liker-1@example.com")
    liker_2 = create_user(db_session, email="milestone-liker-2@example.com")
    liker_3 = create_user(db_session, email="milestone-liker-3@example.com")
    challenge = Challenge(
        user_id=uploader.id,
        category="energy",
        title="Milestone proof",
        description="Milestone proof description",
        difficulty=1,
        status="completed",
    )
    db_session.add(challenge)
    db_session.flush()
    photo = ChallengePhoto(
        challenge_id=challenge.id,
        user_id=uploader.id,
        file_path="milestone.webp",
        upload_rewarded=True,
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)
    state = create_daily_state(db_session, uploader.id, tokens_remaining=15000)

    first_response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker_1),
    )
    second_response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker_2),
    )
    third_response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker_3),
    )

    assert first_response.status_code == 200
    assert first_response.json()["data"]["reward_given"] is False
    assert second_response.status_code == 200
    assert second_response.json()["data"]["reward_given"] is False
    assert third_response.status_code == 200
    assert third_response.json()["data"] == {
        "photo_id": str(photo.id),
        "liked": True,
        "like_count": 3,
        "reward_given": True,
        "reward_amount": 2000,
        "tokens_remaining": 17000,
    }

    db_session.refresh(state)
    assert state.tokens_remaining == 17000
    assert state.like_reward_given == 2000
    assert state.total_reward_given == 2000

    transaction = db_session.scalar(select(TokenTransaction))
    assert transaction is not None
    assert transaction.user_id == uploader.id
    assert transaction.type == "like_reward"
    assert transaction.amount == 2000
    assert transaction.balance_after == 17000
    assert transaction.source_type == "photo"
    assert transaction.source_id == photo.id
    assert transaction.milestone == 3
