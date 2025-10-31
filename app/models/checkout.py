from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.member import Base


class CheckoutStatus(str, enum.Enum):
    CHECKED_OUT = "checked_out"
    RETURNED = "returned"
    OVERDUE = "overdue"
    LOST = "lost"
    CANCELLED = "cancelled"


class Checkout(Base):
    """SQLAlchemy model representing a book loan (checkout)."""

    __tablename__ = "checkouts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    book_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CheckoutStatus] = mapped_column(
        SAEnum(CheckoutStatus, name="checkout_status"),
        nullable=False,
        default=CheckoutStatus.CHECKED_OUT,
        server_default=CheckoutStatus.CHECKED_OUT.value,
    )
    checked_out_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    book = relationship("Book", backref="checkouts")
    member = relationship("Member", backref="checkouts")

    __table_args__ = (
        Index("ix_checkouts_member_status_due", "member_id", "status", "due_at"),
        Index("ix_checkouts_book_status", "book_id", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            "Checkout(id={!r}, book_id={!r}, member_id={!r}, status={!r}, due_at={!r})".format(
                self.id,
                self.book_id,
                self.member_id,
                self.status.value,
                self.due_at,
            )
        )
