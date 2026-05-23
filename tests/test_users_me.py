"""Tests for GET /users/me endpoint."""

from __future__ import annotations

from collections.abc import Generator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models import UserProfile
from app.services.daily_reset import today_kst
from app.services.storage import StorageWriteError, get_file_storage
from tests.conftest import auth_headers, create_user

EXPECTED_FIELDS = {
    "id",
    "email",
    "nickname",
    "profile_image_url",
    "onboarding_completed",
    "profile",
    "today_tokens",
}

UPDATE_RESPONSE_FIELDS = {
    "id",
    "email",
    "nickname",
    "profile_image_url",
    "updated_at",
}


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> str:
        del content_type
        self.files[key] = data
        return key

    def get_url(self, key: str) -> str:
        return f"/files/{key}"

    def delete(self, key: str) -> None:
        self.files.pop(key, None)


class FailingStorage(FakeStorage):
    def put(self, key: str, data: bytes, content_type: str) -> str:
        raise StorageWriteError


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client_with_storage(
    db_session: Session,
    storage: FakeStorage,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_get_file_storage() -> FakeStorage:
        return storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_file_storage] = override_get_file_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def image_upload(
    *,
    content_type: str = "image/png",
    image_format: str = "PNG",
) -> dict[str, tuple[str, bytes, str]]:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color="green").save(buffer, format=image_format)
    return {"profile_image": ("profile.png", buffer.getvalue(), content_type)}


def test_get_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/users/me")

    assert response.status_code == 401


def test_get_me_without_onboarding(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)

    response = client.get("/api/users/me", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == EXPECTED_FIELDS
    assert data["email"] == user.email
    assert data["onboarding_completed"] is False
    assert data["profile"] is None
    assert data["today_tokens"]["date"] == today_kst().isoformat()
    assert data["today_tokens"]["tokens_remaining"] == 150.0


def test_get_me_with_onboarding(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    profile = UserProfile(
        user_id=user.id,
        transport_mode="transit",
        diet_type="omnivore",
        housing_type="apartment",
    )
    db_session.add(profile)
    db_session.commit()

    response = client.get("/api/users/me", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["onboarding_completed"] is True
    assert data["profile"]["transport_mode"] == "transit"
    assert data["profile"]["diet_type"] == "omnivore"
    assert data["profile"]["housing_type"] == "apartment"
    assert data["profile"]["updated_at"] is not None
    assert data["today_tokens"]["tokens_remaining"] == 150.0


def test_update_me_uploads_profile_image(
    client_with_storage: TestClient,
    db_session: Session,
    storage: FakeStorage,
) -> None:
    user = create_user(db_session)

    response = client_with_storage.patch(
        "/api/users/me",
        files=image_upload(),
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == UPDATE_RESPONSE_FIELDS
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["profile_image_url"].startswith("/files/profile-images/")
    assert data["profile_image_url"].endswith(".webp")
    assert data["updated_at"] is not None
    assert len(storage.files) == 1

    db_session.refresh(user)
    assert user.profile_image_url == data["profile_image_url"]


def test_update_me_updates_nickname(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.patch(
        "/api/users/me",
        data={"nickname": "Green User"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == UPDATE_RESPONSE_FIELDS
    assert data["nickname"] == "Green User"
    assert data["profile_image_url"] is None
    assert data["updated_at"] is not None

    db_session.refresh(user)
    assert user.nickname == "Green User"


def test_update_me_rejects_empty_nickname(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.patch(
        "/api/users/me",
        data={"nickname": ""},
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_update_me_rejects_unsupported_profile_image_type(
    client_with_storage: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client_with_storage.patch(
        "/api/users/me",
        files={"profile_image": ("profile.gif", b"GIF89a", "image/gif")},
        headers=auth_headers(user),
    )

    assert response.status_code == 415


def test_update_me_rejects_corrupt_profile_image(
    client_with_storage: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client_with_storage.patch(
        "/api/users/me",
        files={"profile_image": ("profile.png", b"not an image", "image/png")},
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_update_me_storage_failure_returns_502_without_user_change(
    db_session: Session,
) -> None:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_get_file_storage() -> FailingStorage:
        return FailingStorage()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_file_storage] = override_get_file_storage

    user = create_user(db_session)
    try:
        with TestClient(app) as test_client:
            response = test_client.patch(
                "/api/users/me",
                files=image_upload(),
                headers=auth_headers(user),
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    db_session.refresh(user)
    assert user.profile_image_url is None
