"""Challenge photo like service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ChallengePhoto, Like


class ChallengePhotoNotFound(Exception):
    """Raised when a challenge photo does not exist."""


class CannotLikeOwnPhoto(Exception):
    """Raised when a user tries to like their own photo."""


class PhotoAlreadyLiked(Exception):
    """Raised when a user already liked a photo."""


def like_challenge_photo(db: Session, *, user_id: UUID, photo_id: UUID) -> int:
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
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PhotoAlreadyLiked from exc

    return db.scalar(select(func.count(Like.id)).where(Like.photo_id == photo_id)) or 0
