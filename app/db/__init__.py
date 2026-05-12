"""Database session and migration helpers."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Optional

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


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


_engine: Engine | None = None


def configure_database(database_url: Optional[str] = None, engine: Optional[Engine] = None) -> Engine:
    """Configure the process-wide database engine used by SessionLocal."""

    global _engine
    _engine = engine or create_database_engine(database_url)
    SessionLocal.configure(bind=_engine)
    return _engine


def get_engine() -> Engine:
    """Return a lazily configured database engine."""

    if _engine is None:
        return configure_database()
    return _engine


class LazySessionMaker(sessionmaker[Session]):
    """Session factory that binds itself before first use."""

    def __call__(self, **local_kw: object) -> Session:
        if self.kw.get("bind") is None and "bind" not in local_kw:
            configure_database()
        return super().__call__(**local_kw)


SessionLocal = LazySessionMaker(autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependencies."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
