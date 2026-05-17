"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SignupRequest,
    SignupResponse,
)
from app.schemas.common import Errors, error_response
from app.core.security import ACCESS_TOKEN_COOKIE_NAME, JWT_MAX_AGE_SECONDS, is_cookie_secure
from app.services.auth import (
    EmailAlreadyExists,
    InvalidCredentials,
    LoginTemporarilyLocked,
    PasswordPolicyViolation,
    login_user,
    signup_user,
)


router = APIRouter()


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SignupResponse,
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse | JSONResponse:
    try:
        user = signup_user(db, email=payload.email, password=payload.password)
    except EmailAlreadyExists:
        return JSONResponse(
            status_code=Errors.EMAIL_ALREADY_EXISTS.status_code,
            content={
                "code": "EMAIL_ALREADY_EXISTS",
                "message": Errors.EMAIL_ALREADY_EXISTS.message,
            },
        )
    except PasswordPolicyViolation:
        return JSONResponse(
            status_code=Errors.PASSWORD_POLICY_VIOLATION.status_code,
            content={
                "code": "PASSWORD_POLICY_VIOLATION",
                "message": Errors.PASSWORD_POLICY_VIOLATION.message,
            },
        )

    return SignupResponse(
        message="Signup successful",
        user=AuthUserResponse(id=user.id, email=user.email),
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse | JSONResponse:
    client_ip = request.client.host if request.client is not None else "unknown"

    try:
        access_token = login_user(
            db,
            email=payload.email,
            password=payload.password,
            client_ip=client_ip,
        )
    except LoginTemporarilyLocked:
        return error_response(Errors.LOGIN_TEMPORARILY_LOCKED)
    except InvalidCredentials:
        return error_response(Errors.INVALID_CREDENTIALS)

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=JWT_MAX_AGE_SECONDS,
        httponly=True,
        secure=is_cookie_secure(),
        samesite="strict",
    )
    return LoginResponse(message="Login successful")


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response) -> LogoutResponse:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value="",
        max_age=0,
        expires=0,
        httponly=True,
        secure=is_cookie_secure(),
        samesite="strict",
    )
    return LogoutResponse(message="Logout successful")
