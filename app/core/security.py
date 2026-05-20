"""JWT and cookie security configuration."""

from __future__ import annotations

from app.core.config import settings


ACCESS_TOKEN_COOKIE_NAME = "access_token"
JWT_ALGORITHM = "HS256"
JWT_MAX_AGE_SECONDS = 30 * 60
LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
_LOCAL_APP_ENVS = {"dev", "development", "local", "test"}


def get_jwt_secret() -> str:
    return settings.jwt_secret_key


def is_cookie_secure() -> bool:
    return settings.app_env not in _LOCAL_APP_ENVS
