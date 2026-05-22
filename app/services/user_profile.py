"""User profile update business logic."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User
from app.services.storage import FileStorage, StorageWriteError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1280
STORED_CONTENT_TYPE = "image/webp"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


from app.common.exceptions.custom import (
    FileTooLargeException as FileTooLarge,
    InvalidImageException as InvalidImage,
    StorageFailedException as StorageFailed,
    UnsupportedImageTypeException as UnsupportedImageType,
)


def update_user_profile(
    db: Session,
    *,
    user: User,
    nickname: str | None,
    profile_image: UploadFile | None,
    storage: FileStorage,
) -> User:
    stored_key: str | None = None
    profile_image_url: str | None = None

    if profile_image is not None:
        image_bytes = _validate_and_process_image(profile_image)
        storage_key = f"profile-images/{user.id}/{uuid4()}.webp"
        try:
            stored_key = storage.put(storage_key, image_bytes, STORED_CONTENT_TYPE)
        except StorageWriteError as exc:
            raise StorageFailed from exc
        profile_image_url = storage.get_url(stored_key)

    try:
        if nickname is not None:
            user.nickname = nickname
        if profile_image_url is not None:
            user.profile_image_url = profile_image_url
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        if stored_key is not None:
            storage.delete(stored_key)
        raise

    db.refresh(user)
    return user


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
