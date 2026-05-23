"""User service logic."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions.custom import (
    FileTooLargeException as FileTooLarge,
    InvalidImageException as InvalidImage,
    NotFoundException,
    StorageFailedException as StorageFailed,
    UnsupportedImageTypeException as UnsupportedImageType,
)
from app.models import DailyTokenState, User, UserProfile
from app.services.daily_reset import get_or_create_today_state
from app.services.storage import FileStorage, StorageWriteError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1280
STORED_CONTENT_TYPE = "image/webp"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class UserService:
    """현재 사용자 기본 정보와 생활습관 프로필을 처리한다."""

    def __init__(self, db: Session, storage: FileStorage | None = None):
        self.db = db
        self.storage = storage

    def get_me(self, user: User) -> tuple[User, DailyTokenState]:
        state = get_or_create_today_state(self.db, user.id)
        self.db.commit()
        self.db.refresh(state)
        return user, state

    def update_me(
        self,
        user: User,
        *,
        nickname: str | None,
        profile_image: UploadFile | None,
    ) -> User:
        stored_key: str | None = None
        profile_image_url: str | None = None

        if profile_image is not None:
            if self.storage is None:
                raise StorageFailed
            image_bytes = _validate_and_process_profile_image(profile_image)
            storage_key = f"profile-images/{user.id}/{uuid4()}.webp"
            try:
                stored_key = self.storage.put(storage_key, image_bytes, STORED_CONTENT_TYPE)
            except StorageWriteError as exc:
                raise StorageFailed from exc
            profile_image_url = self.storage.get_url(stored_key)

        try:
            if nickname is not None:
                user.nickname = nickname
            if profile_image_url is not None:
                user.profile_image_url = profile_image_url
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            if stored_key is not None and self.storage is not None:
                self.storage.delete(stored_key)
            raise

        self.db.refresh(user)
        return user

    def get_profile(self, user: User) -> UserProfile:
        if user.profile is None:
            raise NotFoundException()
        return user.profile

    def update_profile(
        self,
        user: User,
        *,
        transport_mode: str | None,
        diet_type: str | None,
        housing_type: str | None,
    ) -> UserProfile:
        profile = self.get_profile(user)
        if transport_mode is not None:
            profile.transport_mode = transport_mode
        if diet_type is not None:
            profile.diet_type = diet_type
        if housing_type is not None:
            profile.housing_type = housing_type

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def complete_onboarding(
        self,
        user: User,
        *,
        transport_mode: str,
        diet_type: str,
        housing_type: str,
    ) -> UserProfile:
        if user.profile is None:
            profile = UserProfile(
                user_id=user.id,
                transport_mode=transport_mode,
                diet_type=diet_type,
                housing_type=housing_type,
            )
            self.db.add(profile)
        else:
            profile = user.profile
            profile.transport_mode = transport_mode
            profile.diet_type = diet_type
            profile.housing_type = housing_type

        self.db.commit()
        self.db.refresh(profile)
        return profile


def _validate_and_process_profile_image(upload: UploadFile) -> bytes:
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
