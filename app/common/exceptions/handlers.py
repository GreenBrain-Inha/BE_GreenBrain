from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.common.exceptions.base import AppException
from app.common.response import CommonResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=CommonResponse[None](
                success=False,
                message=exc.message,
                data=None,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Pydantic 검증 실패(422)를 CommonResponse 형식으로 변환한다."""
        return JSONResponse(
            status_code=422,
            content=CommonResponse[None](
                success=False,
                message="입력값이 올바르지 않습니다.",
                data=None,
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """HTTPException을 CommonResponse 형식으로 변환한다."""
        return JSONResponse(
            status_code=exc.status_code,
            content=CommonResponse[None](
                success=False,
                message=str(exc.detail),
                data=None,
            ).model_dump(),
        )
