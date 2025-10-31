from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.member import Base


class Book(Base):
    """SQLAlchemy model representing a library book."""

    __tablename__ = "books"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    isbn: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, unique=True)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    published_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    available_copies: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
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

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Book(id={self.id!r}, title={self.title!r}, author={self.author!r})"
