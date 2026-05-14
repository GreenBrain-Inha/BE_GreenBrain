"""Shared column helpers."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column


def uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )


def timestamp_column() -> Mapped[datetime]:
    return mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
