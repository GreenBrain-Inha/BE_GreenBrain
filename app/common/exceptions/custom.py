from __future__ import annotations

from fastapi import status

from app.common.exceptions.base import AppException


# Auth
class NotAuthenticatedException(AppException):
    def __init__(self, message: str = "인증이 필요합니다."):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class InvalidCredentialsException(AppException):
    def __init__(self, message: str = "이메일 또는 비밀번호가 올바르지 않습니다."):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class EmailAlreadyExistsException(AppException):
    def __init__(self, message: str = "이미 존재하는 이메일입니다."):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


class PasswordPolicyViolationException(AppException):
    def __init__(
        self,
        message: str = "비밀번호는 8자 이상, 대문자·소문자·숫자를 포함하고 72바이트 이하여야 합니다.",
    ):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class LoginTemporarilyLockedException(AppException):
    def __init__(self, message: str = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요."):
        super().__init__(message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


# General
class NotFoundException(AppException):
    def __init__(self, message: str = "리소스를 찾을 수 없습니다."):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND)


class InvalidFieldException(AppException):
    def __init__(self, message: str = "입력값이 올바르지 않습니다."):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


# File / Storage
class FileTooLargeException(AppException):
    def __init__(self, message: str = "파일이 너무 큽니다."):
        super().__init__(message=message, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


class UnsupportedImageTypeException(AppException):
    def __init__(self, message: str = "지원하지 않는 이미지 형식입니다."):
        super().__init__(message=message, status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


class InvalidImageException(AppException):
    def __init__(self, message: str = "유효하지 않은 이미지 파일입니다."):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class StorageFailedException(AppException):
    def __init__(self, message: str = "파일 저장에 실패했습니다."):
        super().__init__(message=message, status_code=status.HTTP_502_BAD_GATEWAY)


# Challenge
class ChallengeNotFoundException(AppException):
    def __init__(self, message: str = "챌린지를 찾을 수 없습니다."):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND)


class ChallengeNotPendingException(AppException):
    def __init__(self, message: str = "수락 대기 상태의 챌린지가 아닙니다."):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


class TokenNotExhaustedException(AppException):
    def __init__(self, message: str = "일일 채팅 토큰이 아직 남아있습니다."):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


class DailyChallengeLimitReachedException(AppException):
    def __init__(self, message: str = "오늘의 챌린지 생성 한도에 도달했습니다."):
        super().__init__(message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


class ChallengeGenerationFailedException(AppException):
    def __init__(self, message: str = "챌린지 생성에 실패했습니다."):
        super().__init__(message=message, status_code=status.HTTP_502_BAD_GATEWAY)


class ChallengeNotOwnedException(AppException):
    def __init__(self, message: str = "본인의 챌린지가 아닙니다."):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN)


class ChallengeNotActiveException(AppException):
    def __init__(self, message: str = "진행 중인 챌린지가 아닙니다."):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


class PhotoAlreadyUploadedException(AppException):
    def __init__(self, message: str = "이미 사진이 업로드된 챌린지입니다."):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


# Challenge Photo
class ChallengePhotoNotFoundException(AppException):
    def __init__(self, message: str = "챌린지 사진을 찾을 수 없습니다."):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND)


class CannotLikeOwnPhotoException(AppException):
    def __init__(self, message: str = "본인의 사진에는 좋아요를 누를 수 없습니다."):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN)


class PhotoAlreadyLikedException(AppException):
    def __init__(self, message: str = "이미 좋아요를 누른 사진입니다."):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


# Chat / Token
class ChatSessionNotFoundException(AppException):
    def __init__(self, message: str = "채팅 세션을 찾을 수 없습니다."):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND)


class TokenExhaustedException(AppException):
    def __init__(self, message: str = "오늘의 채팅 토큰을 모두 사용했습니다."):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN)


class AiProviderException(AppException):
    def __init__(
        self,
        message: str = "AI 응답 생성에 실패했습니다.",
        status_code: int = status.HTTP_502_BAD_GATEWAY,
    ):
        super().__init__(message=message, status_code=status_code)


class AiProviderStatusException(AiProviderException):
    """AI provider가 반환한 HTTP 오류를 클라이언트에 안전하게 전달한다."""

    _PASSTHROUGH_STATUS_CODES = frozenset({400, 401, 403, 404, 429})

    def __init__(self, *, provider_status_code: int, provider_message: str | None = None):
        message = f"AI 제공자 오류({provider_status_code})"
        if provider_message:
            message = f"{message}: {provider_message[:300]}"

        status_code = (
            provider_status_code
            if provider_status_code in self._PASSTHROUGH_STATUS_CODES
            else status.HTTP_502_BAD_GATEWAY
        )
        super().__init__(message=message, status_code=status_code)


class UnsupportedChatModelException(AppException):
    def __init__(self, message: str = "지원하지 않는 채팅 모델입니다."):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST)
