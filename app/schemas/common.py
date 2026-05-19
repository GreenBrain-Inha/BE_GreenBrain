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
    UNSUPPORTED_CHAT_MODEL = ApiError(400, "Unsupported chat model")
    CHAT_SESSION_NOT_FOUND = ApiError(404, "Chat session not found")
    NOT_FOUND = ApiError(404, "Not found")
    CHALLENGE_NOT_FOUND = ApiError(404, "Challenge not found")
    TOKEN_NOT_EXHAUSTED = ApiError(409, "Daily chat tokens are not exhausted")
    CHALLENGE_NOT_PENDING = ApiError(409, "Challenge is not pending acceptance")
    DAILY_CHALLENGE_LIMIT_REACHED = ApiError(429, "Daily challenge limit reached")
    CHALLENGE_GENERATION_FAILED = ApiError(502, "Challenge generation failed")
    CHALLENGE_NOT_OWNED = ApiError(403, "Challenge is not owned by current user")
    CHALLENGE_NOT_ACTIVE = ApiError(409, "Challenge is not active")
    PHOTO_ALREADY_UPLOADED = ApiError(409, "Challenge photo already uploaded")
    CHALLENGE_PHOTO_NOT_FOUND = ApiError(404, "Challenge photo not found")
    CANNOT_LIKE_OWN_PHOTO = ApiError(403, "Cannot like own photo")
    PHOTO_ALREADY_LIKED = ApiError(409, "Challenge photo already liked")
    FILE_TOO_LARGE = ApiError(413, "File is too large")
    UNSUPPORTED_IMAGE_TYPE = ApiError(415, "Unsupported image type")
    INVALID_IMAGE = ApiError(422, "Invalid image")
    STORAGE_WRITE_FAILED = ApiError(502, "Storage write failed")


def error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"message": error.message})
