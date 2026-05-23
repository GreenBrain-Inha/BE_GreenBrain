"""Shared test fixtures and helpers."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import ACCESS_TOKEN_COOKIE_NAME
from app.db import Base, get_db
from app.main import app
from app.models import ChatSession, User
from app.services.auth_service import create_access_token


@pytest.fixture(autouse=True)
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def register_sqlite_functions(dbapi_connection: object, _: object) -> None:
        dbapi_connection.create_function(
            "clock_timestamp",
            0,
            lambda: datetime.now(timezone.utc).isoformat(sep=" "),
        )

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict[str, str]:
    return {"Cookie": f"{ACCESS_TOKEN_COOKIE_NAME}={create_access_token(user.id)}"}


def create_user(
    db_session: Session,
    *,
    email: str = "user@example.com",
) -> User:
    user = User(email=email, password_hash="hashed")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_chat_session(db_session: Session, user: User) -> ChatSession:
    session = ChatSession(user_id=user.id)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session
