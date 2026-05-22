"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.common.response import CommonResponse
from app.db import get_db
from app.schemas.auth import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from app.core.security import ACCESS_TOKEN_COOKIE_NAME, JWT_MAX_AGE_SECONDS, is_cookie_secure
from app.services.auth import login_user, signup_user


router = APIRouter()


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=CommonResponse[SignupResponse],
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> CommonResponse[SignupResponse]:
    user = signup_user(db, email=payload.email, password=payload.password)
    return CommonResponse.success_response(
        message="회원가입이 완료되었습니다.",
        data=SignupResponse(id=user.id, email=user.email),
    )


@router.post("/login", response_model=CommonResponse[LoginResponse])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CommonResponse[LoginResponse]:
    client_ip = request.client.host if request.client is not None else "unknown"
    login_result = login_user(
        db,
        email=payload.email,
        password=payload.password,
        client_ip=client_ip,
    )
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=login_result.access_token,
        max_age=JWT_MAX_AGE_SECONDS,
        httponly=True,
        secure=is_cookie_secure(),
        samesite="strict",
    )
    return CommonResponse.success_response(
        message="로그인되었습니다.",
        data=LoginResponse(onboarding_completed=login_result.onboarding_completed),
    )


@router.post("/logout", response_model=CommonResponse[None])
def logout(response: Response) -> CommonResponse[None]:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value="",
        max_age=0,
        expires=0,
        httponly=True,
        secure=is_cookie_secure(),
        samesite="strict",
    )
    return CommonResponse.success_response(message="로그아웃되었습니다.")
