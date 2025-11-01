from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.settings import SessionSettings, get_session_settings
from app.db.session import get_session
from app.main import app
from app.models import Base
from app.models.member import Member
from app.models.session import Session as SessionModel
from app.security.hash import hash_password


@dataclass
class ClientFixture:
    client: TestClient
    session_factory: sessionmaker
    settings: SessionSettings


@pytest.fixture()
def client_fixture() -> ClientFixture:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def override_get_session() -> Session:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    get_session_settings.cache_clear()

    test_settings = SessionSettings(
        idle_timeout_minutes=1,
        absolute_timeout_hours=1,
        cookie_name="session_id",
        cookie_secure=False,
        cookie_samesite="lax",
        cookie_domain=None,
        cookie_path="/",
        cookie_max_age_seconds=None,
        send_idle_remaining_header=True,
    )

    def override_settings() -> SessionSettings:
        return test_settings

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_session_settings] = override_settings

    with TestClient(app) as client:
        yield ClientFixture(client=client, session_factory=TestingSessionLocal, settings=test_settings)

    app.dependency_overrides.clear()
    get_session_settings.cache_clear()


def _create_member(session: Session, *, email: str, password: str) -> Member:
    member = Member(
        email=email,
        display_name="Example User",
        password_hash=hash_password(password),
    )
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def test_signin_sets_session_cookie_and_allows_access(client_fixture: ClientFixture) -> None:
    with client_fixture.session_factory() as db:
        member = _create_member(db, email="reader@example.com", password="StrongPassword1!")

    response = client_fixture.client.post(
        "/auth/signin",
        json={"email": "reader@example.com", "password": "StrongPassword1!"},
    )
    assert response.status_code == 200
    assert response.json()["member"]["email"] == "reader@example.com"
    assert response.cookies.get(client_fixture.settings.cookie_name) is not None

    me_response = client_fixture.client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "reader@example.com"

    with client_fixture.session_factory() as db:
        sessions = db.query(SessionModel).filter(SessionModel.member_id == member.id).all()
        assert len(sessions) == 1


def test_new_signin_revokes_previous_session(client_fixture: ClientFixture) -> None:
    with client_fixture.session_factory() as db:
        member = _create_member(db, email="single@session.com", password="StrongPassword1!")

    first_response = client_fixture.client.post(
        "/auth/signin",
        json={"email": "single@session.com", "password": "StrongPassword1!"},
    )
    assert first_response.status_code == 200
    first_session_id = first_response.cookies.get(client_fixture.settings.cookie_name)
    assert first_session_id is not None

    second_response = client_fixture.client.post(
        "/auth/signin",
        json={"email": "single@session.com", "password": "StrongPassword1!"},
    )
    assert second_response.status_code == 200
    second_session_id = second_response.cookies.get(client_fixture.settings.cookie_name)
    assert second_session_id is not None
    assert second_session_id != first_session_id

    stale_response = client_fixture.client.get(
        "/auth/me",
        cookies={client_fixture.settings.cookie_name: first_session_id},
    )
    assert stale_response.status_code == 401
    assert stale_response.json()["detail"]["code"] == "invalid_session"

    active_response = client_fixture.client.get(
        "/auth/me",
        cookies={client_fixture.settings.cookie_name: second_session_id},
    )
    assert active_response.status_code == 200
    assert active_response.json()["email"] == "single@session.com"

    with client_fixture.session_factory() as db:
        active_sessions = (
            db.query(SessionModel)
            .filter(SessionModel.member_id == member.id, SessionModel.revoked.is_(False))
            .all()
        )
        assert len(active_sessions) == 1
        revoked_sessions = (
            db.query(SessionModel)
            .filter(SessionModel.member_id == member.id, SessionModel.revoked.is_(True))
            .all()
        )
        assert all(session.revoked_at is not None for session in revoked_sessions)


def test_idle_timeout_revokes_session(client_fixture: ClientFixture) -> None:
    with client_fixture.session_factory() as db:
        member = _create_member(db, email="idle@test.com", password="StrongPassword1!")

    client_fixture.client.post(
        "/auth/signin",
        json={"email": "idle@test.com", "password": "StrongPassword1!"},
    )

    with client_fixture.session_factory() as db:
        session = db.query(SessionModel).filter(SessionModel.member_id == member.id).first()
        assert session is not None
        session.last_active_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        db.add(session)
        db.commit()

    response = client_fixture.client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "idle_expired"


def test_absolute_timeout_revokes_session(client_fixture: ClientFixture) -> None:
    with client_fixture.session_factory() as db:
        member = _create_member(db, email="absolute@test.com", password="StrongPassword1!")

    client_fixture.client.post(
        "/auth/signin",
        json={"email": "absolute@test.com", "password": "StrongPassword1!"},
    )

    with client_fixture.session_factory() as db:
        session = db.query(SessionModel).filter(SessionModel.member_id == member.id).first()
        assert session is not None
        expired_time = datetime.now(timezone.utc) - timedelta(hours=2)
        session.created_at = expired_time
        session.last_active_at = expired_time
        db.add(session)
        db.commit()

    response = client_fixture.client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "absolute_expired"
