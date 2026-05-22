from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CommonResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None

    @classmethod
    def success_response(cls, message: str, data: Optional[T] = None) -> "CommonResponse[T]":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail_response(cls, message: str, data: Optional[T] = None) -> "CommonResponse[T]":
        return cls(success=False, message=message, data=data)
