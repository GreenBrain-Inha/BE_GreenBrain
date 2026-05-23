"""Challenge photo upload business logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Challenge, ChallengePhoto
from app.services.storage import FileStorage, StorageWriteError
from app.services.token_service import TokenService


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1280
STORED_CONTENT_TYPE = "image/webp"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


from app.common.exceptions.custom import (
    ChallengeNotActiveException as ChallengeNotActive,
    ChallengeNotFoundException as ChallengeNotFound,
    ChallengeNotOwnedException as ChallengeNotOwned,
    FileTooLargeException as FileTooLarge,
    InvalidImageException as InvalidImage,
    PhotoAlreadyUploadedException as PhotoAlreadyUploaded,
    StorageFailedException as StorageFailed,
    UnsupportedImageTypeException as UnsupportedImageType,
)


@dataclass(frozen=True)
class ChallengePhotoUploadResult:
    photo: ChallengePhoto
    challenge: Challenge
    file_url: str
    reward_amount: float
    tokens_remaining: float


def upload_challenge_photo(
    db: Session,
    *,
    user_id: UUID,
    challenge_id: UUID,
    upload: UploadFile,
    storage: FileStorage,
) -> ChallengePhotoUploadResult:
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise ChallengeNotFound
    if challenge.user_id != user_id:
        raise ChallengeNotOwned
    if challenge.status != "active":
        raise ChallengeNotActive

    existing_photo = db.scalar(
        select(ChallengePhoto).where(ChallengePhoto.challenge_id == challenge_id)
    )
    if existing_photo is not None:
        raise PhotoAlreadyUploaded

    image_bytes = _validate_and_process_image(upload)
    photo_id = uuid4()
    storage_key = f"challenge-photos/{photo_id}.webp"

    try:
        stored_key = storage.put(storage_key, image_bytes, STORED_CONTENT_TYPE)
    except StorageWriteError as exc:
        raise StorageFailed from exc

    try:
        photo = ChallengePhoto(
            id=photo_id,
            challenge_id=challenge.id,
            user_id=user_id,
            file_path=stored_key,
            upload_rewarded=True,
        )
        challenge.status = "completed"
        challenge.completed_at = datetime.now(timezone.utc)
        db.add(photo)

        token_service = TokenService(db)
        state = token_service.get_or_create_today_state(user_id)
        reward_amount = token_service.grant_upload_reward(
            state=state,
            user_id=user_id,
            photo_id=photo_id,
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        storage.delete(stored_key)
        raise

    db.refresh(photo)
    db.refresh(challenge)
    return ChallengePhotoUploadResult(
        photo=photo,
        challenge=challenge,
        file_url=storage.get_url(stored_key),
        reward_amount=reward_amount,
        tokens_remaining=state.tokens_remaining,
    )


def _validate_and_process_image(upload: UploadFile) -> bytes:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedImageType

    raw = upload.file.read()
    upload.file.seek(0)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise FileTooLarge

    try:
        with Image.open(BytesIO(raw)) as image:
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(
                (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format="WEBP", quality=85)
            return output.getvalue()
    except (OSError, UnidentifiedImageError) as exc:
        raise InvalidImage from exc
