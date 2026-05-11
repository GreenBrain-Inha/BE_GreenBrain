from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    PASSWORD_POLICY_VIOLATION = "PASSWORD_POLICY_VIOLATION"
    LOGIN_TEMPORARILY_LOCKED = "LOGIN_TEMPORARILY_LOCKED"

# 공통 오류 응답 모델
class ErrorResponse(BaseModel):
    code: ErrorCode
    message: str
