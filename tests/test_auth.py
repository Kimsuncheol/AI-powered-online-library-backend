from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session
from app.main import app
from app.models.member import Base
from app.security.hash import hash_password, verify_password
from app.security.jwt import JWTSettings, TokenType, decode_token, get_jwt_settings


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    return engine


@pytest.fixture()
def client(engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def _override_get_session() -> Session:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    test_settings = JWTSettings(
        secret_key="test-secret",
        algorithm="HS256",
        access_token_exp_minutes=60,
        refresh_token_exp_minutes=60 * 24,
        issuer="test-suite",
        audience=None,
    )

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_jwt_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        setattr(test_client, "jwt_settings", test_settings)
        yield test_client

    app.dependency_overrides.clear()


def test_password_hashing_roundtrip():
    password = "s3cureP@ss!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_signup_and_duplicate_email(client: TestClient):
    payload = {
        "email": "user@example.com",
        "displayName": "Example User",
        "password": "strongpassword123",
        "role": "admin",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "user"
    assert "password" not in body
    assert "password_hash" not in body

    duplicate = client.post("/auth/signup", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "member_exists"


def test_signin_wrong_password(client: TestClient):
    payload = {
        "email": "test@example.com",
        "displayName": "Tester",
        "password": "correct-password",
    }
    client.post("/auth/signup", json=payload)

    response = client.post(
        "/auth/signin",
        json={"email": payload["email"], "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"


def test_signin_and_token_decode(client: TestClient):
    payload = {
        "email": "decode@example.com",
        "displayName": "Decoder",
        "password": "decode-password",
    }
    client.post("/auth/signup", json=payload)

    response = client.post(
        "/auth/signin",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["accessToken"]
    token_payload = decode_token(body["accessToken"], client.jwt_settings)
    assert token_payload.token_type == TokenType.ACCESS
    assert token_payload.role == "user"

    headers = {"Authorization": f"Bearer {body['accessToken']}"}
    me_response = client.get("/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == payload["email"]
