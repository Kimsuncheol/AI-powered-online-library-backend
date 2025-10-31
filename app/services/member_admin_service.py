from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.member import Member, MemberRole
from app.schemas.member import (
    MemberCreate,
    MemberOut,
    MemberUpdate,
    create_member_model,
    member_to_schema,
)
from app.security.hash import hash_password


class MemberAdminService:
    """Business logic for administrative member management."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_members(self, skip: int = 0, limit: int = 20, search: Optional[str] = None) -> List[MemberOut]:
        stmt = select(Member).order_by(Member.created_at.desc())

        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Member.email.ilike(pattern),
                    Member.display_name.ilike(pattern),
                )
            )

        stmt = stmt.offset(skip).limit(limit)

        members = self.session.execute(stmt).scalars().all()
        return [member_to_schema(member) for member in members]

    def get_member_by_id(self, member_id: str) -> MemberOut:
        member = self.session.get(Member, member_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "member_not_found", "message": "Member not found."},
            )
        return member_to_schema(member)

    def create_member(self, payload: MemberCreate) -> MemberOut:
        password_hash = hash_password(payload.password)
        member = create_member_model(payload, password_hash=password_hash)
        member.role = MemberRole.USER

        self.session.add(member)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "member_exists", "message": "Email already registered."},
            ) from exc

        self.session.refresh(member)
        return member_to_schema(member)

    def update_member(self, member_id: str, payload: MemberUpdate) -> MemberOut:
        member = self.session.get(Member, member_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "member_not_found", "message": "Member not found."},
            )

        update_data = payload.model_dump(exclude_unset=True)

        if "display_name" in update_data:
            member.display_name = update_data["display_name"]
        if "avatar_url" in update_data:
            member.avatar_url = update_data["avatar_url"]
        if "bio" in update_data:
            member.bio = update_data["bio"]
        if "location" in update_data:
            member.location = update_data["location"]
        if "role" in update_data and update_data["role"] is not None:
            try:
                member.role = MemberRole(update_data["role"])
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": "invalid_role", "message": "Role must be either 'user' or 'admin'."},
                ) from exc

        self.session.add(member)
        self.session.commit()
        self.session.refresh(member)
        return member_to_schema(member)

    def delete_member(self, member_id: str) -> None:
        member = self.session.get(Member, member_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "member_not_found", "message": "Member not found."},
            )

        self.session.delete(member)
        self.session.commit()


def get_member_admin_service(session: Session = Depends(get_session)) -> MemberAdminService:
    return MemberAdminService(session=session)
