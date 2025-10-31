from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.member import get_member_by_email
from app.db.session import get_session
from app.models.member import Member, MemberRole
from app.schemas.member import (
    MemberCreate,
    MemberOut,
    member_to_schema,
    create_member_model,
)
from app.security.hash import hash_password, verify_password
from app.security.jwt import (
    EncodedTokens,
    InvalidTokenError,
    JWTSettings,
    TokenPayload,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt_settings,
)


@dataclass
class AuthResult:
    member: MemberOut
    tokens: EncodedTokens


class AuthService:
    """Business logic for authentication and member lifecycle."""

    def __init__(self, session: Session, settings: JWTSettings) -> None:
        self.session = session
        self.settings = settings

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

    def authenticate(self, email: str, password: str) -> AuthResult:
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

        tokens = self._issue_tokens(member)
        return AuthResult(member=member_to_schema(member), tokens=tokens)

    def get_current_member(self, token: str) -> Member:
        try:
            payload = decode_token(token, self.settings)
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_token", "message": "Unable to validate token."},
            ) from exc

        self._ensure_access_token(payload)
        member = self.session.get(Member, payload.subject)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "member_not_found", "message": "Member no longer exists."},
            )
        return member

    def _issue_tokens(self, member: Member) -> EncodedTokens:
        access = create_access_token(
            subject=member.id,
            role=member.role.value,
            settings=self.settings,
        )
        refresh = create_refresh_token(
            subject=member.id,
            role=member.role.value,
            settings=self.settings,
        )
        return EncodedTokens(access_token=access, refresh_token=refresh)

    @staticmethod
    def _ensure_access_token(payload: TokenPayload) -> None:
        if payload.token_type != TokenType.ACCESS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_token_type", "message": "Access token required."},
            )


def get_auth_service(
    session: Session = Depends(get_session),
    settings: JWTSettings = Depends(get_jwt_settings),
) -> AuthService:
    return AuthService(session=session, settings=settings)
