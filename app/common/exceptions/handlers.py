from __future__ import annotations

from fastapi import FastAPI, Request
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
