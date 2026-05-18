from __future__ import annotations

from collections.abc import Generator

import bcrypt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import User
from app.services import auth as auth_service
from app.services.auth import EmailAlreadyExists, PasswordPolicyViolation


PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 8 characters, include uppercase, lowercase, "
    "and number, and be at most 72 bytes"
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[User.__table__])
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(engine, tables=[User.__table__])
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def get_user_by_email(db_session: Session, email: str) -> User | None:
    return db_session.scalar(select(User).where(User.email == email))


def test_signup_creates_user_with_normalized_email_and_bcrypt_hash(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": " User@Example.COM ", "password": "Password123"},
    )

    assert response.status_code == 201
    assert "set-cookie" not in response.headers
    body = response.json()
    assert body["message"] == "Signup successful"
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["id"]
    assert "password" not in body
    assert "password_hash" not in body
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]

    user = get_user_by_email(db_session, "user@example.com")
    assert user is not None
    assert user.password_hash != "Password123"
    assert bcrypt.checkpw("Password123".encode("utf-8"), user.password_hash.encode("utf-8"))


def test_signup_rejects_duplicate_email_after_normalization(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/api/auth/signup",
        json={"email": "User@Example.COM", "password": "Password123"},
    )
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/auth/signup",
        json={"email": " user@example.com ", "password": "Password123"},
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "message": "Email already exists",
    }


@pytest.mark.parametrize(
    "password",
    [
        "Pass1",
        "password123",
        "PASSWORD123",
        "PasswordOnly",
        "A1" + "a" * 71,
    ],
)
def test_signup_rejects_password_policy_violations(
    client: TestClient,
    db_session: Session,
    password: str,
) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": "user@example.com", "password": password},
    )

    assert response.status_code == 422
    assert response.json() == {
        "message": PASSWORD_POLICY_MESSAGE,
    }
    assert db_session.scalar(sa.select(sa.func.count()).select_from(User)) == 0


def test_invalid_email_uses_request_validation_response(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": "not-an-email", "password": "Password123"},
    )

    assert response.status_code == 422
    assert "detail" in response.json()


def test_password_over_72_bytes_is_rejected_before_hashing(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_hash(_: str) -> str:
        raise AssertionError("hash_password should not be called")

    monkeypatch.setattr(auth_service, "hash_password", fail_hash)

    with pytest.raises(PasswordPolicyViolation):
        auth_service.signup_user(db_session, email="user@example.com", password="A1" + "a" * 71)


def test_signup_maps_unique_constraint_race_to_email_exists(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_integrity_error() -> None:
        raise IntegrityError("insert", {}, Exception("unique violation"))

    monkeypatch.setattr(db_session, "commit", raise_integrity_error)

    with pytest.raises(EmailAlreadyExists):
        auth_service.signup_user(db_session, email="race@example.com", password="Password123")
