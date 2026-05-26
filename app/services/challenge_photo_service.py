"""Challenge photo upload, feed, and like service logic."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.common.exceptions.custom import (
    CannotLikeOwnPhotoException as CannotLikeOwnPhoto,
    ChallengeNotActiveException as ChallengeNotActive,
    ChallengeNotFoundException as ChallengeNotFound,
    ChallengeNotOwnedException as ChallengeNotOwned,
    ChallengePhotoNotFoundException as ChallengePhotoNotFound,
    FileTooLargeException as FileTooLarge,
    InvalidImageException as InvalidImage,
    PhotoAlreadyLikedException as PhotoAlreadyLiked,
    PhotoAlreadyUploadedException as PhotoAlreadyUploaded,
    StorageFailedException as StorageFailed,
    UnsupportedImageTypeException as UnsupportedImageType,
)
from app.models import Challenge, ChallengePhoto, Like, TokenTransaction, User
from app.schemas.challenge import (
    ChallengeFeedItemResponse,
    ChallengeFeedResponse,
    ChallengePhotoLikeResponse,
    ChallengePhotoLikedUserItem,
    ChallengePhotoLikedUsersResponse,
    ChallengePhotoResponse,
    ChallengePhotoUploadChallengeResponse,
    ChallengePhotoUploadResponse,
    ChallengePhotoUploadRewardResponse,
)
from app.services.storage import FileStorage, StorageWriteError, get_file_storage
from app.services.token_service import TokenService


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1280
STORED_CONTENT_TYPE = "image/webp"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ChallengePhotoService:
    """Handle challenge photo upload, feed, and like use cases."""

    def __init__(self, db: Session, storage: FileStorage | None = None):
        self.db = db
        self.storage = storage

    def _require_storage(self) -> FileStorage:
        """Return the configured storage backend only when a use case needs it."""

        if self.storage is None:
            self.storage = get_file_storage()
        return self.storage

    def upload_photo(
        self,
        *,
        user_id: UUID,
        challenge_id: UUID,
        file: UploadFile,
    ) -> ChallengePhotoUploadResponse:
        """Upload a challenge proof photo and apply the upload reward."""

        challenge = self.db.get(Challenge, challenge_id)
        if challenge is None:
            raise ChallengeNotFound
        if challenge.user_id != user_id:
            raise ChallengeNotOwned
        if challenge.status != "active":
            raise ChallengeNotActive

        existing_photo = self.db.scalar(
            select(ChallengePhoto).where(ChallengePhoto.challenge_id == challenge_id)
        )
        if existing_photo is not None:
            raise PhotoAlreadyUploaded

        image_bytes = _validate_and_process_image(file)
        photo_id = uuid4()
        storage_key = _build_storage_key(photo_id)
        storage = self._require_storage()

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
            self.db.add(photo)

            token_service = TokenService(self.db)
            state = token_service.get_or_create_today_state(user_id)
            reward_amount = token_service.grant_upload_reward(
                state=state,
                user_id=user_id,
                photo_id=photo_id,
            )
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            storage.delete(stored_key)
            raise

        self.db.refresh(photo)
        self.db.refresh(challenge)
        return ChallengePhotoUploadResponse(
            photo=ChallengePhotoResponse(
                id=photo.id,
                challenge_id=photo.challenge_id,
                file_url=storage.get_url(stored_key),
                created_at=photo.created_at,
            ),
            challenge=ChallengePhotoUploadChallengeResponse(
                id=challenge.id,
                status=challenge.status,
                completed_at=challenge.completed_at,
            ),
            reward=ChallengePhotoUploadRewardResponse(
                type="upload_reward",
                reward_amount=reward_amount,
                tokens_remaining=state.tokens_remaining,
            ),
        )

    def get_feed(self, *, user_id: UUID, limit: int, offset: int) -> ChallengeFeedResponse:
        """Return challenge photo feed items with like counts and viewer like state."""

        storage = self._require_storage()
        like_counts = (
            select(
                Like.photo_id.label("photo_id"),
                func.count(Like.id).label("like_count"),
            )
            .group_by(Like.photo_id)
            .subquery()
        )
        liked_by_me = (
            select(Like.photo_id.label("photo_id"))
            .where(Like.liker_user_id == user_id)
            .subquery()
        )
        total = self.db.scalar(select(func.count()).select_from(ChallengePhoto)) or 0
        rows = self.db.execute(
            select(
                ChallengePhoto,
                Challenge,
                User,
                func.coalesce(like_counts.c.like_count, 0),
                liked_by_me.c.photo_id.is_not(None),
            )
            .join(Challenge, Challenge.id == ChallengePhoto.challenge_id)
            .join(User, User.id == ChallengePhoto.user_id)
            .outerjoin(like_counts, like_counts.c.photo_id == ChallengePhoto.id)
            .outerjoin(liked_by_me, liked_by_me.c.photo_id == ChallengePhoto.id)
            .order_by(ChallengePhoto.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return ChallengeFeedResponse(
            items=[
                ChallengeFeedItemResponse(
                    photo_id=photo.id,
                    challenge_id=photo.challenge_id,
                    user_id=user.id,
                    nickname=user.nickname,
                    profile_image_url=user.profile_image_url,
                    title=challenge.title,
                    category=challenge.category,
                    photo_url=storage.get_url(photo.file_path),
                    like_count=int(like_count),
                    liked_by_me=bool(liked),
                    carbon_saved_gco2eq=None,
                    created_at=photo.created_at,
                )
                for photo, challenge, user, like_count, liked in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    def like_photo(self, *, user_id: UUID, photo_id: UUID) -> ChallengePhotoLikeResponse:
        """Like another user's challenge photo and grant milestone rewards."""

        photo = self.db.get(ChallengePhoto, photo_id)
        if photo is None:
            raise ChallengePhotoNotFound

        if photo.user_id == user_id:
            raise CannotLikeOwnPhoto

        existing_like = self.db.scalar(
            select(Like).where(
                Like.photo_id == photo_id,
                Like.liker_user_id == user_id,
            )
        )
        if existing_like is not None:
            raise PhotoAlreadyLiked

        self.db.add(Like(photo_id=photo_id, liker_user_id=user_id))
        self.db.flush()
        like_count = (
            self.db.scalar(select(func.count(Like.id)).where(Like.photo_id == photo_id)) or 0
        )

        reward_given = False
        reward_amount = 0.0
        tokens_remaining: float | None = None

        if like_count > 0 and like_count % 3 == 0:
            existing_reward = self.db.scalar(
                select(TokenTransaction).where(
                    TokenTransaction.type == "like_reward",
                    TokenTransaction.source_type == "photo",
                    TokenTransaction.source_id == photo_id,
                    TokenTransaction.milestone == like_count,
                )
            )
            if existing_reward is None:
                token_service = TokenService(self.db)
                state = token_service.get_or_create_today_state(photo.user_id)
                reward_amount = token_service.grant_like_reward(
                    state=state,
                    user_id=photo.user_id,
                    photo_id=photo_id,
                    milestone=like_count,
                )
                reward_given = reward_amount > 0.0
                tokens_remaining = state.tokens_remaining

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise PhotoAlreadyLiked from exc

        return ChallengePhotoLikeResponse(
            photo_id=photo_id,
            liked=True,
            like_count=like_count,
            reward_given=reward_given,
            reward_amount=reward_amount,
            tokens_remaining=tokens_remaining,
        )

    def get_liked_users(
        self,
        *,
        photo_id: UUID,
        limit: int,
        offset: int,
    ) -> ChallengePhotoLikedUsersResponse:
        """특정 인증 사진에 좋아요를 누른 사용자 목록을 최신순으로 조회한다."""

        photo = self.db.get(ChallengePhoto, photo_id)
        if photo is None:
            raise ChallengePhotoNotFound

        total = (
            self.db.scalar(select(func.count()).select_from(Like).where(Like.photo_id == photo_id))
            or 0
        )
        rows = self.db.execute(
            select(Like, User)
            .join(User, User.id == Like.liker_user_id)
            .where(Like.photo_id == photo_id)
            .order_by(Like.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return ChallengePhotoLikedUsersResponse(
            items=[
                ChallengePhotoLikedUserItem(
                    user_id=user.id,
                    nickname=user.nickname,
                    profile_image_url=user.profile_image_url,
                    liked_at=like.created_at,
                )
                for like, user in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    def delete_photo(self, *, user_id: UUID, photo_id: UUID) -> None:
        """본인이 업로드한 인증 사진과 연결된 좋아요를 hard delete한다."""

        photo = self.db.get(ChallengePhoto, photo_id)
        if photo is None:
            raise ChallengePhotoNotFound
        if photo.user_id != user_id:
            raise ChallengeNotOwned

        storage = self._require_storage()
        try:
            storage.delete(photo.file_path)
        except StorageWriteError as exc:
            raise StorageFailed from exc

        self.db.delete(photo)
        self.db.commit()


def _build_storage_key(photo_id: UUID) -> str:
    """Build the storage object key for a challenge proof photo."""

    return f"challenge-photos/{photo_id}.webp"


def _validate_and_process_image(upload: UploadFile) -> bytes:
    """Validate an uploaded image and convert it to bounded WebP bytes."""

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
