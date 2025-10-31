from __future__ import annotations

from typing import Any, Mapping, Optional

from pydantic import BaseModel, EmailStr, Field, ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.member import Member


class _EmailLookup(BaseModel):
    """Internal schema used to validate inbound email lookups."""

    email: EmailStr = Field(max_length=255)


def _validated_email(email: str) -> str:
    """Validate and normalise an email string before use in queries."""
    try:
        payload = _EmailLookup(email=email)
    except ValidationError as exc:
        # Raise a ValueError so callers can translate into domain-specific errors.
        raise ValueError("Invalid email address provided.") from exc
    return payload.email


def get_member_by_email(email: str, db: Session) -> Optional[Member]:
    """
    Fetch a Member using a parameterised ORM query.

    Parameters
    ----------
    email:
        Lookup email captured from user input.
    db:
        Active SQLAlchemy session.
    """

    validated_email = _validated_email(email)
    stmt = select(Member).where(Member.email == validated_email)
    return db.execute(stmt).scalar_one_or_none()


def get_member_credentials_raw(email: str, db: Session) -> Optional[Mapping[str, Any]]:
    """
    Fetch minimal member credentials using a parameterised raw SQL statement.

    The query uses SQLAlchemy's ``text`` construct with named parameters so user input
    is always bound safely and cannot mutate the SQL structure.
    """

    validated_email = _validated_email(email)
    stmt = text(
        "SELECT id, email, password_hash "
        "FROM members "
        "WHERE email = :email"
    )

    return db.execute(stmt, {"email": validated_email}).mappings().one_or_none()

