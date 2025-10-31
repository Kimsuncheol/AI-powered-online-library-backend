from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.session import Session


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy models."""


class MemberRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class Member(Base):
    """SQLAlchemy model representing an application member."""

    __tablename__ = "members"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[MemberRole] = mapped_column(
        SAEnum(MemberRole, name="member_role"),
        nullable=False,
        default=MemberRole.USER,
        server_default=MemberRole.USER.value,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="member",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"Member(id={self.id!r}, email={self.email!r}, "
            f"display_name={self.display_name!r}, role={self.role.value!r})"
        )
