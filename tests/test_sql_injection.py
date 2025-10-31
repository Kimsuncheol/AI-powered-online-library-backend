from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.member import get_member_by_email, get_member_credentials_raw
from app.models.member import Base, Member, MemberRole
from app.security.hash import hash_password


@pytest.fixture()
def db_session() -> Session:
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
    session = TestingSessionLocal()

    member = Member(
        email="reader@example.com",
        display_name="Example Reader",
        password_hash=hash_password("StrongPassword!"),
        role=MemberRole.USER,
    )
    session.add(member)
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_get_member_by_email_returns_expected_member(db_session: Session):
    member = get_member_by_email("reader@example.com", db_session)
    assert member is not None
    assert member.email == "reader@example.com"


def test_get_member_by_email_rejects_sql_injection_attempt(db_session: Session):
    with pytest.raises(ValueError):
        get_member_by_email("' OR 1=1; --", db_session)


def test_raw_sql_execution_uses_bound_parameters(db_session: Session):
    credentials = get_member_credentials_raw("reader@example.com", db_session)
    assert credentials is not None
    assert credentials["email"] == "reader@example.com"

    with pytest.raises(ValueError):
        get_member_credentials_raw("' OR 1=1; --", db_session)

