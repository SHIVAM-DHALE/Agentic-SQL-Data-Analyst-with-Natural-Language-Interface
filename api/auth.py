"""Registration, authentication, and account-recovery routes."""
from __future__ import annotations

import hashlib
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db
from api.email_service import send_password_reset_email
from api.security import (
    ACCESS_TOKEN_MINUTES,
    DUMMY_PASSWORD_HASH,
    PASSWORD_MIN_LENGTH,
    SlidingWindowRateLimiter,
    create_access_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    is_password_reset_token_valid,
    reset_token_expires_at,
    utc_now,
    validate_password_strength,
    verify_password,
)
from database.user_models import PasswordResetToken, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])

PASSWORD_RESET_RESPONSE = (
    "If an account exists for that email, password reset instructions have been sent."
)
INVALID_RESET_RESPONSE = "The password reset link is invalid or has expired."


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


login_rate_limiter = SlidingWindowRateLimiter(
    max_attempts=_positive_int_env("LOGIN_RATE_LIMIT_ATTEMPTS", 10),
    window_seconds=_positive_int_env("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 300),
)
password_reset_rate_limiter = SlidingWindowRateLimiter(
    max_attempts=_positive_int_env("PASSWORD_RESET_RATE_LIMIT_ATTEMPTS", 5),
    window_seconds=_positive_int_env("PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS", 900),
)


def _validate_strong_password(value: str) -> str:
    try:
        return validate_password_strength(value)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)

    _strong_password = field_validator("password")(_validate_strong_password)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Full name is required")
        return normalized


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)

    _strong_password = field_validator("new_password")(_validate_strong_password)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)

    _strong_password = field_validator("new_password")(_validate_strong_password)


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _client_ip(request: Request) -> str:
    # Deliberately do not trust X-Forwarded-For unless a deployment configures
    # its ASGI proxy/trusted-host layer to replace request.client safely.
    return request.client.host if request.client else "unknown"


def _rate_limit_key(scope: str, request: Request, email: str) -> str:
    material = f"{scope}|{_client_ip(request)}|{email}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _enforce_rate_limit(
    limiter: SlidingWindowRateLimiter,
    key: str,
    detail: str,
) -> None:
    allowed, retry_after = limiter.hit(key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = str(payload.email).lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Handles a duplicate-email race between the initial lookup and insert.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    db.refresh(user)
    return public_user(user)


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = str(payload.email).lower().strip()
    limit_key = _rate_limit_key("login", request, email)
    _enforce_rate_limit(
        login_rate_limiter,
        limit_key,
        "Too many login attempts. Please try again later.",
    )

    user = db.scalar(select(User).where(User.email == email))
    password_hash = user.hashed_password if user else DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password, password_hash)
    if not user or not user.is_active or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_rate_limiter.reset(limit_key)
    return {
        "access_token": create_access_token(user.id, user.token_version),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return public_user(current_user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a one-use token without disclosing whether the email exists."""

    email = str(payload.email).lower().strip()
    limit_key = _rate_limit_key("password-reset", request, email)
    _enforce_rate_limit(
        password_reset_rate_limiter,
        limit_key,
        "Too many password reset requests. Please try again later.",
    )

    # Generate a token for both known and unknown emails to keep the observable
    # work more uniform. Only known accounts receive/persist it.
    raw_token, token_hash = generate_password_reset_token()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user:
        now = utc_now()
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=reset_token_expires_at(now),
                request_ip=_client_ip(request)[:45],
            )
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            # Do not change the response and reveal that persistence was
            # attempted for a real account.
            logger.exception("Could not persist a password reset request")
        else:
            background_tasks.add_task(send_password_reset_email, user.email, raw_token)

    return {"message": PASSWORD_RESET_RESPONSE}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Consume a reset token atomically and revoke existing access tokens."""

    token_hash = hash_password_reset_token(payload.token)
    reset_record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    now = utc_now()
    if not reset_record or not is_password_reset_token_valid(
        reset_record.expires_at, reset_record.used_at, now=now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_RESPONSE,
        )

    user = db.get(User, reset_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_RESPONSE,
        )

    reset_record.used_at = now
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != reset_record.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    user.hashed_password = hash_password(payload.new_password)
    user.token_version = int(user.token_version or 0) + 1
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Could not complete a password reset")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is temporarily unavailable. Please try again.",
        ) from exc

    return {
        "message": "Password reset successfully. Sign in with your new password."
    }


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the authenticated user's password and revoke all active JWTs."""

    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    now = utc_now()
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.token_version = int(current_user.token_version or 0) + 1
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == current_user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Could not change an account password")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password change is temporarily unavailable. Please try again.",
        ) from exc

    return {
        "message": "Password changed successfully. Sign in again on all devices."
    }
