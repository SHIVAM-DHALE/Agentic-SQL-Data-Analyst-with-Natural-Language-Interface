"""Database-isolated tests for authentication and account recovery."""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Importing the application models must not require a live PostgreSQL server.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import api.auth as auth_module
from api.auth import router
from api.dependencies import get_db
from api.email_service import build_password_reset_link
from api.security import (
    SlidingWindowRateLimiter,
    create_access_token,
    decode_access_token_claims,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    utc_now,
    validate_password_strength,
    validate_security_configuration,
    verify_password,
)
from database.user_models import Base, PasswordResetToken

GOOD_PASSWORD = "StrongPassword123!"
NEW_PASSWORD = "EvenStrongerPassword456!"


@pytest.fixture(autouse=True)
def clear_rate_limits():
    auth_module.login_rate_limiter.clear()
    auth_module.password_reset_rate_limiter.clear()
    yield
    auth_module.login_rate_limiter.clear()
    auth_module.password_reset_rate_limiter.clear()


@pytest.fixture()
def auth_client(monkeypatch):
    test_engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    Base.metadata.create_all(test_engine)

    application = FastAPI()
    application.include_router(router)

    def override_get_db():
        database = TestingSession()
        try:
            yield database
        finally:
            database.close()

    application.dependency_overrides[get_db] = override_get_db
    delivered_tokens: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_module,
        "send_password_reset_email",
        lambda email, token: delivered_tokens.append((email, token)),
    )

    with TestClient(application) as client:
        yield client, TestingSession, delivered_tokens

    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


def register(client: TestClient, email: str = "analyst@example.com"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Test Analyst",
            "password": GOOD_PASSWORD,
        },
    )


def login(client: TestClient, password: str = GOOD_PASSWORD):
    return client.post(
        "/auth/login",
        json={"email": "analyst@example.com", "password": password},
    )


def test_password_policy_hashing_and_long_passphrase_support():
    with pytest.raises(ValueError):
        validate_password_strength("password")
    with pytest.raises(ValueError):
        validate_password_strength("alllettersbutnonumber")

    validate_password_strength(GOOD_PASSWORD)
    long_password = "LongPassphrase9" + ("x" * 85)
    digest = hash_password(long_password)
    assert verify_password(long_password, digest)
    assert not verify_password("incorrect", digest)
    assert not verify_password(GOOD_PASSWORD, "not-a-valid-password-hash")


def test_access_tokens_include_version_and_reject_expiry():
    token = create_access_token(42, token_version=3)
    claims = decode_access_token_claims(token)
    assert claims["user_id"] == 42
    assert claims["token_version"] == 3

    expired = create_access_token(42, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="Invalid or expired"):
        decode_access_token_claims(expired)


def test_reset_tokens_are_random_hashed_and_expiring():
    raw_one, digest_one = generate_password_reset_token()
    raw_two, digest_two = generate_password_reset_token()
    assert raw_one != raw_two
    assert digest_one != digest_two
    assert raw_one not in digest_one
    assert len(digest_one) == 64
    assert hash_password_reset_token(raw_one) == digest_one


def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_attempts=2, window_seconds=10)
    assert limiter.hit("account", now=1) == (True, 0)
    assert limiter.hit("account", now=2) == (True, 0)
    allowed, retry_after = limiter.hit("account", now=3)
    assert not allowed
    assert retry_after == 8
    assert limiter.hit("account", now=11) == (True, 0)


def test_production_rejects_default_or_short_jwt_secrets():
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_security_configuration("change-this-development-secret", "production")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_security_configuration("short", "prod")
    validate_security_configuration("x" * 32, "production")
    validate_security_configuration("short", "development")


def test_reset_link_url_encodes_token(monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_BASE_URL", "https://app.example/reset?source=email")
    assert build_password_reset_link("a+b/c=") == (
        "https://app.example/reset?source=email&reset_token=a%2Bb%2Fc%3D"
    )


def test_register_login_and_me_are_protected(auth_client):
    client, _, _ = auth_client
    response = register(client)
    assert response.status_code == 201
    assert response.json()["email"] == "analyst@example.com"
    assert "hashed_password" not in response.json()

    assert register(client).status_code == 409
    assert login(client, "WrongPassword999!").status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert client.get(
        "/auth/me", headers={"Authorization": "Bearer invalid-token"}
    ).status_code == 401

    login_response = login(client)
    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    me_response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "user"


def test_forgot_password_is_generic_and_invalidates_older_tokens(auth_client):
    client, TestingSession, delivered_tokens = auth_client
    assert register(client).status_code == 201

    known = client.post(
        "/auth/forgot-password", json={"email": "analyst@example.com"}
    )
    unknown = client.post(
        "/auth/forgot-password", json={"email": "missing@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(delivered_tokens) == 1
    first_raw_token = delivered_tokens[0][1]

    second = client.post(
        "/auth/forgot-password", json={"email": "analyst@example.com"}
    )
    assert second.status_code == 202
    second_raw_token = delivered_tokens[1][1]

    with TestingSession() as database:
        records = database.scalars(
            select(PasswordResetToken).order_by(PasswordResetToken.id)
        ).all()
        assert len(records) == 2
        assert records[0].used_at is not None
        assert records[1].used_at is None
        assert records[1].token_hash != second_raw_token

    old_reset = client.post(
        "/auth/reset-password",
        json={"token": first_raw_token, "new_password": NEW_PASSWORD},
    )
    assert old_reset.status_code == 400

    current_reset = client.post(
        "/auth/reset-password",
        json={"token": second_raw_token, "new_password": NEW_PASSWORD},
    )
    assert current_reset.status_code == 200
    assert client.post(
        "/auth/reset-password",
        json={"token": second_raw_token, "new_password": GOOD_PASSWORD},
    ).status_code == 400
    assert login(client).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200


def test_expired_reset_token_is_rejected(auth_client):
    client, TestingSession, delivered_tokens = auth_client
    register(client)
    client.post("/auth/forgot-password", json={"email": "analyst@example.com"})
    raw_token = delivered_tokens[0][1]

    with TestingSession() as database:
        record = database.scalar(select(PasswordResetToken))
        record.expires_at = utc_now() - timedelta(seconds=1)
        database.commit()

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert "invalid or has expired" in response.json()["detail"]


def test_change_password_revokes_existing_token(auth_client):
    client, _, _ = auth_client
    register(client)
    access_token = login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    wrong = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "WrongPassword999!", "new_password": NEW_PASSWORD},
    )
    assert wrong.status_code == 400

    changed = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": GOOD_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert login(client).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200
