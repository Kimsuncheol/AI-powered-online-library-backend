from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_session
from app.main import app
from app.models.member import Base
from app.security.hash import hash_password, verify_password
from app.core.settings import SessionSettings, get_session_settings


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

    app.dependency_overrides[get_session] = _override_get_session
    get_session_settings.cache_clear()
    test_settings = SessionSettings(
        idle_timeout_minutes=30,
        absolute_timeout_hours=24,
        cookie_name="session_id",
        cookie_secure=False,
        cookie_samesite="lax",
        cookie_domain=None,
        cookie_path="/",
        cookie_max_age_seconds=None,
        send_idle_remaining_header=True,
    )
    app.dependency_overrides[get_session_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        setattr(test_client, "session_settings", test_settings)
        yield test_client

    app.dependency_overrides.clear()
    get_session_settings.cache_clear()


def test_password_hashing_roundtrip():
    password = "s3cureP@ss!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_signup_and_duplicate_email(client: TestClient):
    payload = {
        "email": "user@example.com",
        "displayName": "Example User",
        "password": "Str0ngPassword!",
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
        "password": "CorrectPass1!",
    }
    client.post("/auth/signup", json=payload)

    response = client.post(
        "/auth/signin",
        json={"email": payload["email"], "password": "WrongPass1!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"


def test_signup_rejects_weak_password(client: TestClient):
    payload = {
        "email": "weak@example.com",
        "displayName": "Weak User",
        "password": "weakpass",
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


def test_signin_sets_cookie_and_authorizes_me(client: TestClient):
    payload = {
        "email": "decode@example.com",
        "displayName": "Decoder",
        "password": "DecodePass1!",
    }
    client.post("/auth/signup", json=payload)

    response = client.post(
        "/auth/signin",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["member"]["email"] == payload["email"]
    assert response.cookies.get(client.session_settings.cookie_name)

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == payload["email"]


def test_me_requires_session_cookie(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"
