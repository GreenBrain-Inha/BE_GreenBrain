"""Authentication service logic."""

from __future__ import annotations

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User


PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 8 characters, include uppercase, lowercase, "
    "and number, and be at most 72 bytes"
)


class EmailAlreadyExists(Exception):
    """Raised when a normalized email is already registered."""


class PasswordPolicyViolation(Exception):
    """Raised when a password does not satisfy the signup policy."""


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
