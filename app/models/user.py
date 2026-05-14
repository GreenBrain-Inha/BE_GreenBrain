"""User and UserProfile models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import timestamp_column, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(sa.String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String, nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    created_at: Mapped[datetime] = timestamp_column()
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="user")
    daily_token_states: Mapped[list["DailyTokenState"]] = relationship(back_populates="user")
    token_transactions: Mapped[list["TokenTransaction"]] = relationship(back_populates="user")


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
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    user: Mapped[User] = relationship(back_populates="profile")
