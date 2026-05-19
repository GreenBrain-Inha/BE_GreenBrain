"""Challenge photo like service."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ChallengePhoto, Like, TokenTransaction
from app.services.daily_reset import get_or_create_today_state
from app.services.token_account import grant_like_reward


class ChallengePhotoNotFound(Exception):
    """Raised when a challenge photo does not exist."""


class CannotLikeOwnPhoto(Exception):
    """Raised when a user tries to like their own photo."""


class PhotoAlreadyLiked(Exception):
    """Raised when a user already liked a photo."""


@dataclass(frozen=True)
class ChallengePhotoLikeResult:
    photo_id: UUID
    like_count: int
    reward_given: bool
    reward_amount: float
    tokens_remaining: float | None


def like_challenge_photo(db: Session, *, user_id: UUID, photo_id: UUID) -> ChallengePhotoLikeResult:
    photo = db.get(ChallengePhoto, photo_id)
    if photo is None:
        raise ChallengePhotoNotFound

    if photo.user_id == user_id:
        raise CannotLikeOwnPhoto

    existing_like = db.scalar(
        select(Like).where(
            Like.photo_id == photo_id,
            Like.liker_user_id == user_id,
        )
    )
    if existing_like is not None:
        raise PhotoAlreadyLiked

    db.add(Like(photo_id=photo_id, liker_user_id=user_id))
    db.flush()
    like_count = db.scalar(select(func.count(Like.id)).where(Like.photo_id == photo_id)) or 0

    reward_given = False
    reward_amount = 0.0
    tokens_remaining: float | None = None

    if like_count > 0 and like_count % 3 == 0:
        existing_reward = db.scalar(
            select(TokenTransaction).where(
                TokenTransaction.type == "like_reward",
                TokenTransaction.source_type == "photo",
                TokenTransaction.source_id == photo_id,
                TokenTransaction.milestone == like_count,
            )
        )
        if existing_reward is None:
            state = get_or_create_today_state(db, photo.user_id)
            reward_amount = grant_like_reward(
                db,
                state=state,
                user_id=photo.user_id,
                photo_id=photo_id,
                milestone=like_count,
            )
            reward_given = reward_amount > 0.0
            tokens_remaining = state.tokens_remaining

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PhotoAlreadyLiked from exc

    return ChallengePhotoLikeResult(
        photo_id=photo_id,
        like_count=like_count,
        reward_given=reward_given,
        reward_amount=reward_amount,
        tokens_remaining=tokens_remaining,
    )
