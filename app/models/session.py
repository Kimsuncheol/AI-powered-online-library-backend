from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.member import Base, Member


class Session(Base):
    """Persistent session tied to a signed-in member."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_member_id_last_active_at", "member_id", "last_active_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    member_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_addr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    member: Mapped[Member] = relationship("Member", back_populates="sessions")
