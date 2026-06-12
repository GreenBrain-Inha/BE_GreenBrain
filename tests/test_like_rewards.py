"""Tests for challenge photo like milestone rewards."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Challenge, ChallengePhoto, DailyTokenState, Like, TokenTransaction, User
from app.services.token_service import today_kst
from tests.conftest import auth_headers, create_user


def create_challenge_photo(
    db_session: Session,
    user: User,
    *,
    created_at: datetime | None = None,
) -> ChallengePhoto:
    timestamp = created_at or datetime(2026, 5, 19, 9, 0, tzinfo=timezone.utc)
    challenge = Challenge(
        user_id=user.id,
        category="energy",
        title="Like reward proof",
        description="Like reward proof description",
        difficulty=2,
        status="completed",
        completed_at=timestamp,
    )
    db_session.add(challenge)
    db_session.flush()

    photo = ChallengePhoto(
        challenge_id=challenge.id,
        user_id=user.id,
        file_path="like-reward.webp",
        upload_rewarded=True,
        created_at=timestamp,
    )
    db_session.add(photo)
    db_session.commit()
    db_session.refresh(photo)
    return photo


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


def test_like_counts_one_and_two_do_not_grant_reward(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="reward-uploader@example.com")
    first_liker = create_user(db_session, email="reward-liker-1@example.com")
    second_liker = create_user(db_session, email="reward-liker-2@example.com")
    photo = create_challenge_photo(db_session, uploader)
    create_daily_state(db_session, uploader, tokens_remaining=8000)

    first_response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(first_liker),
    )
    second_response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(second_liker),
    )

    assert first_response.status_code == 200
    assert first_response.json()["data"] == {
        "photo_id": str(photo.id),
        "liked": True,
        "like_count": 1,
        "reward_given": False,
        "reward_amount": 0.0,
        "tokens_remaining": None,
    }
    assert second_response.status_code == 200
    assert second_response.json()["data"]["like_count"] == 2
    assert second_response.json()["data"]["reward_given"] is False
    assert second_response.json()["data"]["reward_amount"] == 0.0
    assert second_response.json()["data"]["tokens_remaining"] is None
    assert db_session.scalars(select(TokenTransaction)).all() == []


def test_third_like_grants_reward_to_photo_uploader_and_records_transaction(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="third-uploader@example.com")
    liker_1 = create_user(db_session, email="third-liker-1@example.com")
    liker_2 = create_user(db_session, email="third-liker-2@example.com")
    liker_3 = create_user(db_session, email="third-liker-3@example.com")
    photo = create_challenge_photo(db_session, uploader)
    state = create_daily_state(db_session, uploader, tokens_remaining=10000)
    db_session.add_all(
        [
            Like(photo_id=photo.id, liker_user_id=liker_1.id),
            Like(photo_id=photo.id, liker_user_id=liker_2.id),
        ]
    )
    db_session.commit()

    response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker_3),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "photo_id": str(photo.id),
        "liked": True,
        "like_count": 3,
        "reward_given": True,
        "reward_amount": 2000,
        "tokens_remaining": 12000,
    }
    assert type(data["reward_amount"]) is int
    assert type(data["tokens_remaining"]) is int

    db_session.refresh(state)
    assert state.tokens_remaining == 12000
    assert state.like_reward_given == 2000
    assert state.total_reward_given == 2000

    transaction = db_session.scalar(select(TokenTransaction))
    assert transaction is not None
    assert transaction.user_id == uploader.id
    assert transaction.type == "like_reward"
    assert transaction.amount == 2000
    assert transaction.balance_after == 12000
    assert transaction.source_type == "photo"
    assert transaction.source_id == photo.id
    assert transaction.milestone == 3


def test_like_reward_can_recover_tokens_above_daily_base_amount(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="cap-uploader@example.com")
    liker_1 = create_user(db_session, email="cap-liker-1@example.com")
    liker_2 = create_user(db_session, email="cap-liker-2@example.com")
    liker_3 = create_user(db_session, email="cap-liker-3@example.com")
    photo = create_challenge_photo(db_session, uploader)
    state = create_daily_state(db_session, uploader, tokens_remaining=14000)
    db_session.add_all(
        [
            Like(photo_id=photo.id, liker_user_id=liker_1.id),
            Like(photo_id=photo.id, liker_user_id=liker_2.id),
        ]
    )
    db_session.commit()

    response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker_3),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "photo_id": str(photo.id),
        "liked": True,
        "like_count": 3,
        "reward_given": True,
        "reward_amount": 2000,
        "tokens_remaining": 16000,
    }
    db_session.refresh(state)
    assert state.tokens_remaining == 16000
    assert state.like_reward_given == 2000
    assert state.total_reward_given == 2000

    transaction = db_session.scalar(select(TokenTransaction))
    assert transaction is not None
    assert transaction.amount == 2000
    assert transaction.balance_after == 16000
    assert transaction.milestone == 3


def test_like_reward_is_granted_when_tokens_are_already_at_daily_base_amount(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="base-uploader@example.com")
    liker_1 = create_user(db_session, email="base-liker-1@example.com")
    liker_2 = create_user(db_session, email="base-liker-2@example.com")
    liker_3 = create_user(db_session, email="base-liker-3@example.com")
    photo = create_challenge_photo(db_session, uploader)
    state = create_daily_state(db_session, uploader, tokens_remaining=15000)
    db_session.add_all(
        [
            Like(photo_id=photo.id, liker_user_id=liker_1.id),
            Like(photo_id=photo.id, liker_user_id=liker_2.id),
        ]
    )
    db_session.commit()

    response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker_3),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
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
    assert transaction.amount == 2000
    assert transaction.balance_after == 17000
    assert transaction.milestone == 3


def test_existing_milestone_transaction_prevents_duplicate_reward(
    client: TestClient,
    db_session: Session,
) -> None:
    uploader = create_user(db_session, email="duplicate-reward-uploader@example.com")
    liker_1 = create_user(db_session, email="duplicate-reward-liker-1@example.com")
    liker_2 = create_user(db_session, email="duplicate-reward-liker-2@example.com")
    liker_3 = create_user(db_session, email="duplicate-reward-liker-3@example.com")
    photo = create_challenge_photo(db_session, uploader)
    state = create_daily_state(db_session, uploader, tokens_remaining=10000)
    db_session.add_all(
        [
            Like(photo_id=photo.id, liker_user_id=liker_1.id),
            Like(photo_id=photo.id, liker_user_id=liker_2.id),
            TokenTransaction(
                user_id=uploader.id,
                daily_state_date=state.date,
                type="like_reward",
                amount=2000,
                balance_after=10000,
                source_type="photo",
                source_id=photo.id,
                milestone=3,
                memo="Existing milestone reward",
            ),
        ]
    )
    db_session.commit()

    response = client.post(
        f"/api/challenge-photos/{photo.id}/like",
        headers=auth_headers(liker_3),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "photo_id": str(photo.id),
        "liked": True,
        "like_count": 3,
        "reward_given": False,
        "reward_amount": 0.0,
        "tokens_remaining": None,
    }
    db_session.refresh(state)
    assert state.tokens_remaining == 10000
    transactions = db_session.scalars(
        select(TokenTransaction).where(
            TokenTransaction.type == "like_reward",
            TokenTransaction.source_id == photo.id,
            TokenTransaction.milestone == 3,
        )
    ).all()
    assert len(transactions) == 1
