"""Password, JWT, reset-token, and lightweight rate-limit helpers.

The helpers in this module deliberately have no database dependency.  This
keeps the security-critical pieces easy to test and lets the API enforce the
same policy for registration, password reset, and password changes.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEVELOPMENT_SECRET = "change-this-development-secret"
ALGORITHM = "HS256"
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}
ACCESS_TOKEN_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60"))
PASSWORD_RESET_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES", "30"))
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "10"))


def validate_security_configuration(
    secret_key: str | None = None,
    environment: str | None = None,
) -> None:
    """Reject unsafe JWT configuration when the application is in production."""

    value = secret_key if secret_key is not None else os.getenv("JWT_SECRET_KEY", "")
    current_environment = (environment or APP_ENV).strip().lower()
    if current_environment not in {"prod", "production"}:
        return

    insecure_values = {
        "",
        DEVELOPMENT_SECRET,
        "change-me",
        "change-me-to-a-long-random-value",
        "replace-with-a-long-random-secret",
    }
    if value.strip().lower() in insecure_values or len(value.encode("utf-8")) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be a unique random value of at least 32 bytes in production"
        )


_configured_secret = os.getenv("JWT_SECRET_KEY", "")
validate_security_configuration(_configured_secret, APP_ENV)
SECRET_KEY = _configured_secret or DEVELOPMENT_SECRET
RESET_TOKEN_PEPPER = os.getenv("PASSWORD_RESET_TOKEN_PEPPER") or SECRET_KEY

# bcrypt_sha256 safely accepts passphrases longer than bcrypt's 72-byte input
# limit.  Plain bcrypt remains enabled so accounts created by older versions
# continue to verify and are transparently upgraded on the next password change.
password_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)

_COMMON_PASSWORDS = {
    "1234567890",
    "letmein123",
    "password1",
    "password123",
    "qwerty123",
    "welcome123",
}


def validate_password_strength(password: str) -> str:
    """Validate a practical password policy and return the unchanged password."""

    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters")
    if password.casefold() in _COMMON_PASSWORDS:
        raise ValueError("Choose a less common password")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must include at least one letter and one number")
    return password


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password without allowing malformed hashes to crash a request."""

    try:
        return password_context.verify(password, hashed_password)
    except (TypeError, ValueError):
        return False


# Used for a password verification even when an account does not exist.  This
# reduces the timing difference between unknown-email and wrong-password logins.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: int,
    token_version: int = 0,
    *,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    """Create a short-lived access token tied to the user's token version."""

    issued_at = now or utc_now()
    expires = issued_at + (expires_delta or timedelta(minutes=ACCESS_TOKEN_MINUTES))
    claims = {
        "sub": str(user_id),
        "ver": int(token_version),
        "type": "access",
        "iat": issued_at,
        "exp": expires,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token_claims(token: str) -> dict[str, Any]:
    """Decode and normalize access-token claims.

    Tokens created by the immediately previous release did not include ``ver``
    or ``type``.  They are treated as version zero for a smooth migration; any
    password reset/change increments the database version and revokes them.
    """

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("type")
        if token_type not in {None, "access"}:
            raise ValueError("Unexpected token type")
        user_id = int(payload["sub"])
        token_version = int(payload.get("ver", 0))
        if user_id <= 0 or token_version < 0:
            raise ValueError("Invalid token claims")
        payload["user_id"] = user_id
        payload["token_version"] = token_version
        return payload
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid or expired access token") from exc


def decode_access_token(token: str) -> int:
    """Backward-compatible helper returning only the authenticated user id."""

    return int(decode_access_token_claims(token)["user_id"])


def generate_password_reset_token() -> tuple[str, str]:
    """Return a high-entropy raw reset token and the digest safe to persist."""

    raw_token = secrets.token_urlsafe(48)
    return raw_token, hash_password_reset_token(raw_token)


def hash_password_reset_token(raw_token: str) -> str:
    """Hash a reset token with a server-side pepper before database lookup."""

    if not raw_token or len(raw_token) > 512:
        # Returning a normal digest for malformed input keeps route behavior
        # uniform while avoiding unbounded attacker-controlled hashing input.
        raw_token = "invalid-reset-token"
    return hmac.new(
        RESET_TOKEN_PEPPER.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def reset_token_expires_at(now: datetime | None = None) -> datetime:
    return (now or utc_now()) + timedelta(minutes=PASSWORD_RESET_MINUTES)


def is_password_reset_token_valid(
    expires_at: datetime,
    used_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Check expiry/single-use state while tolerating legacy naive timestamps."""

    current = now or utc_now()
    expiry = expires_at
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return used_at is None and expiry > current


class SlidingWindowRateLimiter:
    """Small thread-safe in-process limiter for login and reset endpoints.

    This is intentionally dependency-free and suitable for one API process. A
    shared Redis-backed limiter should replace it when deploying multiple API
    workers; the route contract does not need to change.
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        if max_attempts < 1 or window_seconds < 1:
            raise ValueError("Rate-limit settings must be positive")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.max_attempts:
                retry_after = max(1, math.ceil(events[0] + self.window_seconds - current))
                return False, retry_after
            events.append(current)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        """Clear all buckets; primarily useful for isolated tests."""

        with self._lock:
            self._events.clear()
