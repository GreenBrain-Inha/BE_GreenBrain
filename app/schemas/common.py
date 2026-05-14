from __future__ import annotations

from dataclasses import dataclass

from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class ApiError:
    status_code: int
    message: str


class Errors:
    NOT_AUTHENTICATED = ApiError(401, "Authentication required")
    INVALID_CREDENTIALS = ApiError(401, "Invalid email or password")
    EMAIL_ALREADY_EXISTS = ApiError(409, "Email already exists")
    PASSWORD_POLICY_VIOLATION = ApiError(
        422,
        "Password must be at least 8 characters, include uppercase, lowercase, "
        "and number, and be at most 72 bytes",
    )
    LOGIN_TEMPORARILY_LOCKED = ApiError(429, "Too many failed login attempts. Try again later.")
    TOKEN_EXHAUSTED = ApiError(403, "Daily chat tokens are exhausted")
    AI_PROVIDER_ERROR = ApiError(502, "AI provider failed to generate a response")
    CHAT_SESSION_NOT_FOUND = ApiError(404, "Chat session not found")
    NOT_FOUND = ApiError(404, "Not found")


def error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"message": error.message})
