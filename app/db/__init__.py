"""Database session and migration helpers."""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_database_url() -> str:
    """Return the configured synchronous database URL."""

    database_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL or DB_URL must be configured")
    return database_url


def create_database_engine(database_url: Optional[str] = None) -> Engine:
    """Create a synchronous SQLAlchemy engine."""

    return create_engine(database_url or get_database_url(), pool_pre_ping=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False)
