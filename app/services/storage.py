"""File storage service interfaces."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


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
        self.base_dir = Path(base_dir or os.getenv("LOCAL_STORAGE_DIR", "var/uploads"))
        self.base_url = (base_url or os.getenv("LOCAL_STORAGE_BASE_URL", "/uploads")).rstrip("/")

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


def get_file_storage() -> FileStorage:
    return LocalFileStorage()
