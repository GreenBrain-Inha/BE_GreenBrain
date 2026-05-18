"""File storage service interfaces."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageWriteError(Exception):
    """Raised when a file cannot be written to storage."""


class FileStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Store bytes and return the stored key."""

    def get_url(self, key: str) -> str:
        """Return a client-usable URL for a stored key."""

    def delete(self, key: str) -> None:
        """Delete a stored key if it exists."""


class LocalFileStorage:
    def __init__(
        self,
        *,
        base_dir: str | Path | None = None,
        base_url: str | None = None,
    ) -> None:
        self.base_dir = Path(base_dir or settings.local_storage_dir)
        self.base_url = (base_url or settings.local_storage_base_url).rstrip("/")

    def put(self, key: str, data: bytes, content_type: str) -> str:
        del content_type
        target = self._target_path(key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as exc:
            raise StorageWriteError from exc
        return key

    def get_url(self, key: str) -> str:
        normalized = key.replace("\\", "/")
        return f"{self.base_url}/{normalized}"

    def delete(self, key: str) -> None:
        try:
            self._target_path(key).unlink(missing_ok=True)
        except OSError:
            pass

    def _target_path(self, key: str) -> Path:
        normalized = key.replace("\\", "/").lstrip("/")
        target = (self.base_dir / normalized).resolve()
        base = self.base_dir.resolve()
        if base != target and base not in target.parents:
            raise StorageWriteError
        return target


class SupabaseStorage:
    def __init__(
        self,
        *,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        bucket: str | None = None,
        public_base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.supabase_url = (supabase_url or settings.supabase_url).rstrip("/")
        self.service_role_key = service_role_key or settings.supabase_service_role_key
        self.bucket = (bucket or settings.supabase_storage_bucket).strip("/")
        self.public_base_url = (
            public_base_url or settings.supabase_storage_public_base_url
        ).rstrip("/")
        self.client = client or httpx.Client(timeout=10.0, trust_env=False)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        normalized_key = self._normalize_key(key)
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": content_type,
            "x-upsert": "false",
        }
        try:
            response = self.client.post(
                self._object_url(normalized_key),
                content=data,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageWriteError(
                f"Failed to upload {normalized_key} to Supabase Storage"
            ) from exc
        return normalized_key

    def get_url(self, key: str) -> str:
        normalized_key = self._normalize_key(key)
        return f"{self.public_base_url}/{self.bucket}/{quote(normalized_key, safe='/')}"

    def delete(self, key: str) -> None:
        normalized_key = self._normalize_key(key)
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self.client.request(
                "DELETE",
                f"{self.supabase_url}/storage/v1/object/{quote(self.bucket, safe='')}",
                json={"prefixes": [normalized_key]},
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning(
                "Failed to delete %s from Supabase Storage",
                normalized_key,
                exc_info=True,
            )

    def _object_url(self, key: str) -> str:
        return (
            f"{self.supabase_url}/storage/v1/object/"
            f"{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        )

    def _normalize_key(self, key: str) -> str:
        normalized = key.replace("\\", "/").lstrip("/")
        if not normalized or normalized == "." or ".." in normalized.split("/"):
            raise StorageWriteError
        return normalized


def get_file_storage() -> FileStorage:
    backend = settings.storage_backend
    if backend == "local":
        return LocalFileStorage()
    if backend == "supabase":
        return SupabaseStorage()
    raise RuntimeError(f"Unsupported storage backend: {backend}")
