from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.member import Member, MemberRole


class MemberBase(BaseModel):
    email: EmailStr
    display_name: str = Field(alias="displayName")
    avatar_url: Optional[str] = Field(default=None, alias="avatarUrl")
    bio: Optional[str] = None
    location: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class MemberOut(MemberBase):
    id: str
    role: MemberRole
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        use_enum_values=True,
    )


class MemberCreate(MemberBase):
    password: str = Field(repr=False)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class MemberLogin(BaseModel):
    email: EmailStr
    password: str = Field(repr=False)

    model_config = ConfigDict(extra="forbid")


class MemberUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, alias="displayName")
    avatar_url: Optional[str] = Field(default=None, alias="avatarUrl")
    bio: Optional[str] = None
    location: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


def member_to_schema(member: Member) -> MemberOut:
    """Convert a SQLAlchemy Member instance to a MemberOut schema."""
    return MemberOut.model_validate(member)


def create_member_model(payload: MemberCreate, password_hash: str) -> Member:
    """Instantiate a Member ORM object from a validated MemberCreate payload."""
    return Member(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=password_hash,
        avatar_url=payload.avatar_url,
        bio=payload.bio,
        location=payload.location,
    )
