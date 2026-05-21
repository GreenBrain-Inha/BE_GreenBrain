"""Tests for GET /users/me endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import UserProfile
from app.services.daily_reset import today_kst
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


def test_get_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/users/me")

    assert response.status_code == 401


def test_get_me_without_onboarding(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)

    response = client.get("/api/users/me", headers=auth_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == EXPECTED_FIELDS
    assert body["email"] == user.email
    assert body["onboarding_completed"] is False
    assert body["profile"] is None
    assert body["today_tokens"]["date"] == today_kst().isoformat()
    assert body["today_tokens"]["tokens_remaining"] == 150.0


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
    body = response.json()
    assert body["onboarding_completed"] is True
    assert body["profile"] == {
        "transport_mode": "transit",
        "diet_type": "omnivore",
        "housing_type": "apartment",
    }
    assert body["today_tokens"]["tokens_remaining"] == 150.0


def test_update_me_updates_profile_image_url(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.patch(
        "/api/users/me",
        json={"profile_image_url": "https://example.com/profile.png"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == UPDATE_RESPONSE_FIELDS
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert body["profile_image_url"] == "https://example.com/profile.png"
    assert body["updated_at"] is not None

    db_session.refresh(user)
    assert user.profile_image_url == "https://example.com/profile.png"


def test_update_me_updates_nickname(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.patch(
        "/api/users/me",
        json={"nickname": "Green User"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == UPDATE_RESPONSE_FIELDS
    assert body["nickname"] == "Green User"
    assert body["profile_image_url"] is None
    assert body["updated_at"] is not None

    db_session.refresh(user)
    assert user.nickname == "Green User"


def test_update_me_rejects_empty_nickname(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.patch(
        "/api/users/me",
        json={"nickname": ""},
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_update_me_rejects_invalid_profile_image_url(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.patch(
        "/api/users/me",
        json={"profile_image_url": "not-a-url"},
        headers=auth_headers(user),
    )

    assert response.status_code == 422
