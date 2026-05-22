"""Authentication service logic."""

from __future__ import annotations

import bcrypt
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import Cookie, Depends

from app.db import get_db
from app.core.security import (
    ACCESS_TOKEN_COOKIE_NAME,
    JWT_ALGORITHM,
    JWT_MAX_AGE_SECONDS,
    LOGIN_LOCKOUT_SECONDS,
    LOGIN_MAX_FAILED_ATTEMPTS,
    get_jwt_secret,
)
from app.models import User


PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 8 characters, include uppercase, lowercase, "
    "and number, and be at most 72 bytes"
)


from app.common.exceptions.custom import (
    EmailAlreadyExistsException as EmailAlreadyExists,
    InvalidCredentialsException as InvalidCredentials,
    LoginTemporarilyLockedException as LoginTemporarilyLocked,
    PasswordPolicyViolationException as PasswordPolicyViolation,
)


@dataclass
class LoginAttemptState:
    failed_count: int = 0
    locked_until: datetime | None = None


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    onboarding_completed: bool


_login_attempts: dict[tuple[str, str], LoginAttemptState] = {}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_password_policy(password: str) -> None:
    if (
        len(password) < 8
        or len(password.encode("utf-8")) > 72
        or not any(character.isupper() for character in password)
        or not any(character.islower() for character in password)
        or not any(character.isdigit() for character in password)
    ):
        raise PasswordPolicyViolation


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: UUID, *, now: datetime | None = None) -> str:
    issued_at = now or _utcnow()
    expires_at = issued_at + timedelta(seconds=JWT_MAX_AGE_SECONDS)
    payload = {
        "sub": str(user_id),
        "iat": int(issued_at.timestamp()),
        "exp": expires_at,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _attempt_key(email: str, client_ip: str) -> tuple[str, str]:
    return normalize_email(email), client_ip or "unknown"


def reset_login_attempts() -> None:
    _login_attempts.clear()


def _get_active_attempt_state(key: tuple[str, str], now: datetime) -> LoginAttemptState:
    state = _login_attempts.setdefault(key, LoginAttemptState())
    if state.locked_until is not None and state.locked_until <= now:
        state.failed_count = 0
        state.locked_until = None
    return state


def _ensure_not_locked(key: tuple[str, str], now: datetime) -> None:
    state = _get_active_attempt_state(key, now)
    if state.locked_until is not None and state.locked_until > now:
        raise LoginTemporarilyLocked


def _record_failed_login(key: tuple[str, str], now: datetime) -> bool:
    state = _get_active_attempt_state(key, now)
    state.failed_count += 1
    if state.failed_count > LOGIN_MAX_FAILED_ATTEMPTS:
        state.locked_until = now + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
        return True
    return False


def _record_successful_login(key: tuple[str, str]) -> None:
    _login_attempts.pop(key, None)


def signup_user(db: Session, *, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    validate_password_policy(password)

    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise EmailAlreadyExists

    user = User(email=normalized_email, password_hash=hash_password(password))
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyExists from exc

    db.refresh(user)
    return user


def get_current_user(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
) -> User:
    from app.common.exceptions.custom import NotAuthenticatedException

    if access_token is None:
        raise NotAuthenticatedException()
    try:
        payload = jwt.decode(access_token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise NotAuthenticatedException()
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise NotAuthenticatedException()

    user = db.get(User, user_id)
    if user is None:
        raise NotAuthenticatedException()
    return user


def login_user(db: Session, *, email: str, password: str, client_ip: str) -> LoginResult:
    normalized_email = normalize_email(email)
    key = _attempt_key(normalized_email, client_ip)
    now = _utcnow()
    _ensure_not_locked(key, now)

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(password, user.password_hash):
        if _record_failed_login(key, now):
            raise LoginTemporarilyLocked
        raise InvalidCredentials

    _record_successful_login(key)
    return LoginResult(
        access_token=create_access_token(user.id, now=now),
        onboarding_completed=user.profile is not None,
    )
