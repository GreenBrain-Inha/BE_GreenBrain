"""Tests for user lifestyle profile endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import UserProfile
from tests.conftest import auth_headers, create_user


def test_get_profile_returns_404_without_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.get("/api/users/profile", headers=auth_headers(user))

    assert response.status_code == 404


def test_get_profile_returns_current_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    profile = UserProfile(
        user_id=user.id,
        transport_mode="transit",
        diet_type="omnivore",
        housing_type="apartment",
    )
    db_session.add(profile)
    db_session.commit()

    response = client.get("/api/users/profile", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["transport_mode"] == "transit"
    assert data["diet_type"] == "omnivore"
    assert data["housing_type"] == "apartment"
    assert data["updated_at"] is not None


def test_update_profile_returns_404_without_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.patch(
        "/api/users/profile",
        json={"transport_mode": "walk"},
        headers=auth_headers(user),
    )

    assert response.status_code == 404


def test_update_profile_updates_partial_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    profile = UserProfile(
        user_id=user.id,
        transport_mode="transit",
        diet_type="omnivore",
        housing_type="apartment",
    )
    db_session.add(profile)
    db_session.commit()

    response = client.patch(
        "/api/users/profile",
        json={"diet_type": "vegetarian"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["transport_mode"] == "transit"
    assert data["diet_type"] == "vegetarian"
    assert data["housing_type"] == "apartment"
    assert data["updated_at"] is not None

    db_session.refresh(profile)
    assert profile.transport_mode == "transit"
    assert profile.diet_type == "vegetarian"
    assert profile.housing_type == "apartment"


def test_update_profile_rejects_invalid_enum_value(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    profile = UserProfile(
        user_id=user.id,
        transport_mode="transit",
        diet_type="omnivore",
        housing_type="apartment",
    )
    db_session.add(profile)
    db_session.commit()

    response = client.patch(
        "/api/users/profile",
        json={"transport_mode": "subway"},
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_onboarding_creates_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.post(
        "/api/users/onboarding",
        json={
            "transport_mode": "walk",
            "diet_type": "vegetarian",
            "housing_type": "house",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["transport_mode"] == "walk"
    assert data["diet_type"] == "vegetarian"
    assert data["housing_type"] == "house"
    assert data["updated_at"] is not None

    profile = db_session.get(UserProfile, user.id)
    assert profile is not None
    assert profile.transport_mode == "walk"
    assert profile.diet_type == "vegetarian"
    assert profile.housing_type == "house"


def test_onboarding_rejects_invalid_enum_value(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = client.post(
        "/api/users/onboarding",
        json={
            "transport_mode": "walk",
            "diet_type": "keto",
            "housing_type": "house",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_onboarding_updates_existing_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    profile = UserProfile(
        user_id=user.id,
        transport_mode="car",
        diet_type="omnivore",
        housing_type="apartment",
    )
    db_session.add(profile)
    db_session.commit()

    response = client.post(
        "/api/users/onboarding",
        json={
            "transport_mode": "transit",
            "diet_type": "vegetarian",
            "housing_type": "house",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["transport_mode"] == "transit"
    assert data["diet_type"] == "vegetarian"
    assert data["housing_type"] == "house"
    assert data["updated_at"] is not None

    db_session.refresh(profile)
    assert profile.transport_mode == "transit"
    assert profile.diet_type == "vegetarian"
    assert profile.housing_type == "house"
