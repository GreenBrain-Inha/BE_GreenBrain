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
    def app_env(self) -> str:
        return os.getenv("APP_ENV", "prod").strip().lower()


settings = Settings()
