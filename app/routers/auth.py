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
from app.schemas.common import ErrorCode
from app.services.auth import (
    ACCESS_TOKEN_COOKIE_NAME,
    JWT_MAX_AGE_SECONDS,
    PASSWORD_POLICY_MESSAGE,
    EmailAlreadyExists,
    InvalidCredentials,
    LoginTemporarilyLocked,
    PasswordPolicyViolation,
    login_user,
    signup_user,
)

from app.core.config import access_token_cookie_secure

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
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": ErrorCode.EMAIL_ALREADY_EXISTS.value,
                "message": "Email already exists",
            },
        )
    except PasswordPolicyViolation:
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.PASSWORD_POLICY_VIOLATION.value,
                "message": PASSWORD_POLICY_MESSAGE,
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
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "code": ErrorCode.LOGIN_TEMPORARILY_LOCKED.value,
                "message": "Too many failed login attempts. Try again later.",
            },
        )
    except InvalidCredentials:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": ErrorCode.INVALID_CREDENTIALS.value,
                "message": "Invalid email or password",
            },
        )

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=JWT_MAX_AGE_SECONDS,
        httponly=True,
        secure=access_token_cookie_secure(),
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
        secure=True,
        samesite="strict",
    )
    return LogoutResponse(message="Logout successful")
