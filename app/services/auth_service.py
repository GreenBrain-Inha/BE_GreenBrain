"""Authentication service logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import ClassVar
from uuid import UUID

import bcrypt
from fastapi import Cookie, Depends
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions.custom import (
    EmailAlreadyExistsException as EmailAlreadyExists,
    InvalidCredentialsException as InvalidCredentials,
    LoginTemporarilyLockedException as LoginTemporarilyLocked,
    NotAuthenticatedException,
    PasswordPolicyViolationException as PasswordPolicyViolation,
)
from app.core.security import (
    ACCESS_TOKEN_COOKIE_NAME,
    JWT_ALGORITHM,
    JWT_MAX_AGE_SECONDS,
    LOGIN_LOCKOUT_SECONDS,
    LOGIN_MAX_FAILED_ATTEMPTS,
    get_jwt_secret,
)
from app.db import get_db
from app.models import User


def create_access_token(user_id: UUID, *, now: datetime | None = None) -> str:
    """사용자 ID를 subject로 하는 access token JWT를 생성한다."""

    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=JWT_MAX_AGE_SECONDS)
    payload = {
        "sub": str(user_id),
        "iat": int(issued_at.timestamp()),
        "exp": expires_at,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


@dataclass
class LoginAttemptState:
    """이메일과 IP 조합별 로그인 실패 횟수와 잠금 만료 시각을 보관한다."""

    failed_count: int = 0
    locked_until: datetime | None = None


class AuthService:
    """회원가입과 로그인 인증을 처리하는 서비스."""

    _login_attempts: ClassVar[dict[tuple[str, str], LoginAttemptState]] = {}

    def __init__(self, db: Session):
        """요청 단위 DB 세션을 서비스 인스턴스에 연결한다."""

        self.db = db

    @staticmethod
    def _normalize_email(email: str) -> str:
        """중복 검사와 로그인을 위해 이메일 비교 형식을 통일한다."""

        return email.strip().lower()

    @staticmethod
    def _validate_password_policy(password: str) -> None:
        """회원가입 비밀번호가 보안 정책을 만족하는지 검증한다."""

        if (
            len(password) < 8
            or len(password.encode("utf-8")) > 72
            or not any(character.isupper() for character in password)
            or not any(character.islower() for character in password)
            or not any(character.isdigit() for character in password)
        ):
            raise PasswordPolicyViolation

    @staticmethod
    def _hash_password(password: str) -> str:
        """평문 비밀번호를 bcrypt hash 문자열로 변환한다."""

        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """입력 비밀번호가 저장된 bcrypt hash와 일치하는지 확인한다."""

        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    @classmethod
    def _get_active_attempt_state(
        cls,
        key: tuple[str, str],
        now: datetime,
    ) -> LoginAttemptState:
        """잠금이 만료된 로그인 실패 상태를 초기화하고 현재 상태를 반환한다."""

        state = cls._login_attempts.setdefault(key, LoginAttemptState())
        if state.locked_until is not None and state.locked_until <= now:
            state.failed_count = 0
            state.locked_until = None
        return state

    @classmethod
    def _ensure_not_locked(cls, key: tuple[str, str], now: datetime) -> None:
        """현재 이메일/IP 조합이 잠금 상태면 로그인 시도를 차단한다."""

        state = cls._get_active_attempt_state(key, now)
        if state.locked_until is not None and state.locked_until > now:
            raise LoginTemporarilyLocked

    @classmethod
    def _record_failed_login(cls, key: tuple[str, str], now: datetime) -> bool:
        """실패 횟수를 누적하고 잠금 기준을 넘었는지 반환한다."""

        state = cls._get_active_attempt_state(key, now)
        state.failed_count += 1
        if state.failed_count > LOGIN_MAX_FAILED_ATTEMPTS:
            state.locked_until = now + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
            return True
        return False

    @classmethod
    def _record_successful_login(cls, key: tuple[str, str]) -> None:
        """로그인 성공 시 해당 이메일/IP 조합의 실패 상태를 제거한다."""

        cls._login_attempts.pop(key, None)

    def signup(self, *, email: str, password: str) -> User:
        """이메일과 비밀번호를 검증한 뒤 신규 사용자를 생성한다."""

        normalized_email = self._normalize_email(email)
        self._validate_password_policy(password)

        existing_user = self.db.scalar(select(User).where(User.email == normalized_email))
        if existing_user is not None:
            raise EmailAlreadyExists

        user = User(email=normalized_email, password_hash=self._hash_password(password))
        self.db.add(user)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EmailAlreadyExists from exc

        self.db.refresh(user)
        return user

    def login(self, *, email: str, password: str, client_ip: str) -> tuple[str, bool]:
        """이메일/비밀번호를 검증하고 access token과 온보딩 완료 여부를 반환한다."""

        normalized_email = self._normalize_email(email)
        key = normalized_email, client_ip or "unknown"
        now = datetime.now(timezone.utc)
        self._ensure_not_locked(key, now)

        user = self.db.scalar(select(User).where(User.email == normalized_email))
        if user is None or not self._verify_password(password, user.password_hash):
            if self._record_failed_login(key, now):
                raise LoginTemporarilyLocked
            raise InvalidCredentials

        self._record_successful_login(key)
        return create_access_token(user.id, now=now), user.profile is not None


def get_current_user(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
) -> User:
    """인증 쿠키의 JWT를 검증하고 현재 사용자 모델을 반환한다."""

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
