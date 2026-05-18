"""Tests for file storage implementations."""

from __future__ import annotations

import httpx
import pytest

from app.services.storage import (
    LocalFileStorage,
    StorageWriteError,
    SupabaseStorage,
    get_file_storage,
)


def test_get_file_storage_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)

    storage = get_file_storage()

    assert isinstance(storage, LocalFileStorage)


def test_get_file_storage_selects_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://project-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "challenge-photos")
    monkeypatch.setenv(
        "SUPABASE_STORAGE_PUBLIC_BASE_URL",
        "https://project-ref.supabase.co/storage/v1/object/public",
    )
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

    storage = get_file_storage()

    assert isinstance(storage, SupabaseStorage)


def test_get_file_storage_supabase_ignores_invalid_ssl_cert_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://project-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "challenge-photos")
    monkeypatch.setenv(
        "SUPABASE_STORAGE_PUBLIC_BASE_URL",
        "https://project-ref.supabase.co/storage/v1/object/public",
    )
    monkeypatch.setenv("SSL_CERT_FILE", "C:/does/not/exist/cacert.pem")

    storage = get_file_storage()

    assert isinstance(storage, SupabaseStorage)


def test_get_file_storage_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "unknown")

    with pytest.raises(RuntimeError, match="Unsupported storage backend: unknown"):
        get_file_storage()


def test_get_file_storage_requires_supabase_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_STORAGE_PUBLIC_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="SUPABASE_URL must be set"):
        get_file_storage()


def test_supabase_storage_get_url_includes_public_base_bucket_and_key() -> None:
    storage = SupabaseStorage(
        supabase_url="https://project-ref.supabase.co",
        service_role_key="service-role",
        bucket="challenge-photos",
        public_base_url="https://project-ref.supabase.co/storage/v1/object/public/",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        ),
    )

    assert storage.get_url("uuid.webp") == (
        "https://project-ref.supabase.co/storage/v1/object/public/"
        "challenge-photos/uuid.webp"
    )


def test_supabase_storage_put_uploads_without_network() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"Key": "uuid.webp"})

    storage = SupabaseStorage(
        supabase_url="https://project-ref.supabase.co",
        service_role_key="service-role",
        bucket="challenge-photos",
        public_base_url="https://project-ref.supabase.co/storage/v1/object/public",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    stored_key = storage.put("uuid.webp", b"image-bytes", "image/webp")

    assert stored_key == "uuid.webp"
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == (
        "https://project-ref.supabase.co/storage/v1/object/"
        "challenge-photos/uuid.webp"
    )
    assert request.headers["apikey"] == "service-role"
    assert request.headers["authorization"] == "Bearer service-role"
    assert request.headers["content-type"] == "image/webp"
    assert request.headers["x-upsert"] == "false"
    assert request.content == b"image-bytes"


def test_supabase_storage_put_rejects_duplicate_prefix_key() -> None:
    storage = SupabaseStorage(
        supabase_url="https://project-ref.supabase.co",
        service_role_key="service-role",
        bucket="challenge-photos",
        public_base_url="https://project-ref.supabase.co/storage/v1/object/public",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        ),
    )

    stored_key = storage.put("uuid.webp", b"image-bytes", "image/webp")

    assert stored_key == "uuid.webp"


def test_supabase_storage_put_raises_storage_write_error_on_failure() -> None:
    storage = SupabaseStorage(
        supabase_url="https://project-ref.supabase.co",
        service_role_key="service-role",
        bucket="challenge-photos",
        public_base_url="https://project-ref.supabase.co/storage/v1/object/public",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ),
    )

    with pytest.raises(StorageWriteError):
        storage.put("uuid.webp", b"image-bytes", "image/webp")


def test_supabase_storage_delete_ignores_failure() -> None:
    storage = SupabaseStorage(
        supabase_url="https://project-ref.supabase.co",
        service_role_key="service-role",
        bucket="challenge-photos",
        public_base_url="https://project-ref.supabase.co/storage/v1/object/public",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(500))
        ),
    )

    storage.delete("uuid.webp")
