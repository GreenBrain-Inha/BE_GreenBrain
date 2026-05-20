"""Authentication API schemas."""

from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, field_validator


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value.strip()):
            raise ValueError("Invalid email")
        return value


class AuthUserResponse(BaseModel):
    id: UUID
    email: str


class SignupResponse(BaseModel):
    message: str
    user: AuthUserResponse


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value.strip()):
            raise ValueError("Invalid email")
        return value


class LoginResponse(BaseModel):
    message: str
    onboarding_completed: bool


class LogoutResponse(BaseModel):
    message: str
