"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )


def timestamp_column() -> Mapped[datetime]:
    return mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(sa.String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String, nullable=False)
    created_at: Mapped[datetime] = timestamp_column()

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    messages: Mapped[list["Message"]] = relationship(back_populates="user")
    daily_token_states: Mapped[list["DailyTokenState"]] = relationship(back_populates="user")
    token_transactions: Mapped[list["TokenTransaction"]] = relationship(back_populates="user")
    challenges: Mapped[list["Challenge"]] = relationship(back_populates="user")
    challenge_photos: Mapped[list["ChallengePhoto"]] = relationship(back_populates="user")
    likes: Mapped[list["Like"]] = relationship(back_populates="liker")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    transport_mode: Mapped[str] = mapped_column(sa.String, nullable=False)
    diet_type: Mapped[str] = mapped_column(sa.String, nullable=False)
    housing_type: Mapped[str] = mapped_column(sa.String, nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(sa.String, nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    carbon_gco2eq: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    created_at: Mapped[datetime] = timestamp_column()

    user: Mapped[User] = relationship(back_populates="messages")


class DailyTokenState(Base):
    __tablename__ = "daily_token_state"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    tokens_remaining: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
        default=150.0,
        server_default=sa.text("150.0"),
    )
    upload_reward_given: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
        default=0.0,
        server_default=sa.text("0.0"),
    )
    like_reward_given: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
        default=0.0,
        server_default=sa.text("0.0"),
    )
    total_reward_given: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
        default=0.0,
        server_default=sa.text("0.0"),
    )
    challenge_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    user: Mapped[User] = relationship(back_populates="daily_token_states")


class TokenTransaction(Base):
    __tablename__ = "token_transactions"
    __table_args__ = (
        sa.Index(
            "uq_token_transactions_like_reward_milestone",
            "source_type",
            "source_id",
            "milestone",
            unique=True,
            postgresql_where=sa.text("type = 'like_reward'"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    daily_state_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    type: Mapped[str] = mapped_column(sa.String, nullable=False)
    amount: Mapped[float] = mapped_column(sa.Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(sa.Float, nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    source_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    milestone: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    memo: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = timestamp_column()

    user: Mapped[User] = relationship(back_populates="token_transactions")


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
    completed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="challenges")
    photo: Mapped["ChallengePhoto"] = relationship(back_populates="challenge", uselist=False)


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
    user: Mapped[User] = relationship(back_populates="challenge_photos")
    likes: Mapped[list["Like"]] = relationship(back_populates="photo")


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (
        sa.UniqueConstraint("photo_id", "liker_user_id", name="uq_likes_photo_id_liker_user_id"),
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
    liker: Mapped[User] = relationship(back_populates="likes")
