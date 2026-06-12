"""DailyTokenState and TokenTransaction models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import timestamp_column, uuid_pk


class DailyTokenState(Base):
    __tablename__ = "daily_token_state"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    tokens_remaining: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=15_000,
        server_default=sa.text("15000"),
    )
    upload_reward_given: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    like_reward_given: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    total_reward_given: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
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

    user: Mapped["User"] = relationship(back_populates="daily_token_states")


class TokenTransaction(Base):
    __tablename__ = "token_transactions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "daily_state_date"],
            ["daily_token_state.user_id", "daily_token_state.date"],
            ondelete="CASCADE",
        ),
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
    amount: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    source_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    milestone: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    memo: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = timestamp_column()

    user: Mapped["User"] = relationship(back_populates="token_transactions")
