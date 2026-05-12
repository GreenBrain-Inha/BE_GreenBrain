"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.auth import AuthUserResponse, SignupRequest, SignupResponse
from app.schemas.common import ErrorCode
from app.services.auth import (
    PASSWORD_POLICY_MESSAGE,
    EmailAlreadyExists,
    PasswordPolicyViolation,
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
