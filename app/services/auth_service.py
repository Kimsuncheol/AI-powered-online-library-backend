from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.member import get_member_by_email
from app.db.session import get_session
from app.models.member import Member, MemberRole
from app.schemas.member import MemberCreate, MemberOut, create_member_model, member_to_schema
from app.security.hash import hash_password, verify_password


class AuthService:
    """Business logic for authentication and member lifecycle."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def register_member(self, data: MemberCreate) -> MemberOut:
        existing_member = get_member_by_email(data.email, self.session)
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "member_exists", "message": "Email already registered."},
            )

        password_hash = hash_password(data.password)
        member = create_member_model(data, password_hash=password_hash)
        member.role = MemberRole.USER

        self.session.add(member)
        self.session.commit()
        self.session.refresh(member)

        return member_to_schema(member)

    def authenticate(self, email: str, password: str) -> Member:
        try:
            member = get_member_by_email(email, self.session)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_email", "message": "Invalid email address."},
            ) from exc

        if not member or not verify_password(password, member.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_credentials", "message": "Invalid email or password."},
            )

        return member


def get_auth_service(
    session: Session = Depends(get_session),
) -> AuthService:
    return AuthService(session=session)
