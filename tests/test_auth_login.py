from __future__ import annotations

from collections.abc import Generator
from http.cookies import SimpleCookie
from uuid import UUID

import bcrypt
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import User, UserProfile
from app.common.exceptions.custom import (
    InvalidCredentialsException as InvalidCredentials,
    LoginTemporarilyLockedException as LoginTemporarilyLocked,
)
from app.services.auth_service import AuthService


INVALID_CREDENTIALS_BODY = {
    "success": False,
    "message": "이메일 또는 비밀번호가 올바르지 않습니다.",
    "data": None,
}

LOCKED_BODY = {
    "success": False,
    "message": "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    "data": None,
}


@pytest.fixture(autouse=True)
def reset_login_attempts(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    AuthService._login_attempts.clear()
    yield
    AuthService._login_attempts.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[User.__table__, UserProfile.__table__])
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(engine, tables=[UserProfile.__table__, User.__table__])
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_user(
    db_session: Session,
    *,
    email: str = "user@example.com",
    password: str = "Password123",
) -> User:
    user = User(
        email=email,
        password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        ),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def parse_set_cookie(response: object) -> SimpleCookie:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie


def test_login_sets_local_httponly_jwt_cookie(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, email="user@example.com", password="Password123")

    response = client.post(
        "/api/auth/login",
        json={"email": " User@Example.COM ", "password": "Password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "로그인되었습니다."
    assert body["data"]["onboarding_completed"] is False

    set_cookie = response.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" not in set_cookie
    assert "Max-Age=1800" in set_cookie
    assert "SameSite=strict" in set_cookie

    cookie = parse_set_cookie(response)
    token = cookie["access_token"].value
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["sub"] == str(user.id)
    assert UUID(payload["sub"]) == user.id


def test_login_returns_onboarding_completed_for_profiled_user(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, email="user@example.com", password="Password123")
    db_session.add(
        UserProfile(
            user_id=user.id,
            transport_mode="transit",
            diet_type="omnivore",
            housing_type="apartment",
        )
    )
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["onboarding_completed"] is True
    assert "access_token=" in response.headers["set-cookie"]


def test_login_sets_secure_cookie_in_production(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    create_user(db_session, email="user@example.com", password="Password123")

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )

    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("missing@example.com", "Password123"),
        ("user@example.com", "WrongPassword123"),
    ],
)
def test_login_returns_same_error_for_unknown_email_and_wrong_password(
    client: TestClient,
    db_session: Session,
    email: str,
    password: str,
) -> None:
    create_user(db_session, email="user@example.com", password="Password123")

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS_BODY
    assert "onboarding_completed" not in response.json()
    assert "set-cookie" not in response.headers


def test_login_locks_after_more_than_five_failures(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session, email="user@example.com", password="Password123")

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "WrongPassword123"},
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword123"},
    )

    assert locked_response.status_code == 429
    assert locked_response.json() == LOCKED_BODY
    assert "set-cookie" not in locked_response.headers

    correct_password_response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert correct_password_response.status_code == 429


def test_successful_login_resets_failure_counter(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session, email="user@example.com", password="Password123")

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "WrongPassword123"},
        )
        assert response.status_code == 401

    success_response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert success_response.status_code == 200

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "WrongPassword123"},
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword123"},
    )
    assert locked_response.status_code == 429


def test_lockout_is_scoped_by_email_and_ip(db_session: Session) -> None:
    create_user(db_session, email="user@example.com", password="Password123")
    service = AuthService(db_session)

    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            service.login(
                email="user@example.com",
                password="WrongPassword123",
                client_ip="203.0.113.10",
            )

    with pytest.raises(LoginTemporarilyLocked):
        service.login(
            email="user@example.com",
            password="WrongPassword123",
            client_ip="203.0.113.10",
        )

    with pytest.raises(LoginTemporarilyLocked):
        service.login(
            email="user@example.com",
            password="Password123",
            client_ip="203.0.113.10",
        )

    token, _ = service.login(
        email="user@example.com",
        password="Password123",
        client_ip="203.0.113.11",
    )
    assert token


def test_logout_expires_access_token_cookie(client: TestClient) -> None:
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "로그아웃되었습니다."
    assert body["data"] is None

    set_cookie = response.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" not in set_cookie
    assert "SameSite=strict" in set_cookie
