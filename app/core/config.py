"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os


def _require(key: str, *aliases: str) -> str:
    for name in (key, *aliases):
        value = os.getenv(name)
        if value:
            return value
    raise RuntimeError(f"{key} must be set in environment")


class Settings:
    @property
    def database_url(self) -> str:
        return _require("DATABASE_URL", "DB_URL")

    @property
    def jwt_secret_key(self) -> str:
        return _require("JWT_SECRET_KEY", "JWT_SECRET")

    @property
    def openai_api_key(self) -> str:
        return _require("OPENAI_API_KEY")

    @property
    def runyour_api_key(self) -> str:
        return _require("RUNYOUR_API_KEY")

    @property
    def app_env(self) -> str:
        return os.getenv("APP_ENV", "prod").strip().lower()

    @property
    def allowed_origins(self) -> list[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "")
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def storage_backend(self) -> str:
        return os.getenv("STORAGE_BACKEND", "local").strip().lower()

    @property
    def local_storage_dir(self) -> str:
        return os.getenv("LOCAL_STORAGE_DIR", "var/uploads")

    @property
    def local_storage_base_url(self) -> str:
        return os.getenv("LOCAL_STORAGE_BASE_URL", "/uploads")

    @property
    def supabase_url(self) -> str:
        return _require("SUPABASE_URL")

    @property
    def supabase_service_role_key(self) -> str:
        return _require("SUPABASE_SERVICE_ROLE_KEY")

    @property
    def supabase_storage_bucket(self) -> str:
        return os.getenv("SUPABASE_STORAGE_BUCKET", "challenge-photos")

    @property
    def supabase_storage_public_base_url(self) -> str:
        return _require("SUPABASE_STORAGE_PUBLIC_BASE_URL")


settings = Settings()
