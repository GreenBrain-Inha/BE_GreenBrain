"""Challenge, challenge photo, and like models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import timestamp_column, uuid_pk


class Challenge(Base):
    __tablename__ = "challenges"
    __table_args__ = (
        sa.Index(
            "uq_challenges_one_open_per_user",
            "user_id",
            unique=True,
            postgresql_where=sa.text("status IN ('pending_acceptance', 'active')"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(sa.String, nullable=False)
    title: Mapped[str] = mapped_column(sa.String, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String, nullable=False)
    created_at: Mapped[datetime] = timestamp_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="challenges")
    photo: Mapped[Optional["ChallengePhoto"]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
    )


class ChallengePhoto(Base):
    __tablename__ = "challenge_photos"

    id: Mapped[UUID] = uuid_pk()
    challenge_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(sa.String, nullable=False)
    upload_rewarded: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    created_at: Mapped[datetime] = timestamp_column()

    challenge: Mapped[Challenge] = relationship(back_populates="photo")
    user: Mapped["User"] = relationship(back_populates="challenge_photos")
    likes: Mapped[list["Like"]] = relationship(
        back_populates="photo",
        cascade="all, delete-orphan",
    )


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (
        sa.UniqueConstraint(
            "photo_id",
            "liker_user_id",
            name="uq_likes_photo_id_liker_user_id",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    photo_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("challenge_photos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    liker_user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = timestamp_column()

    photo: Mapped[ChallengePhoto] = relationship(back_populates="likes")
    liker: Mapped["User"] = relationship(back_populates="likes")
