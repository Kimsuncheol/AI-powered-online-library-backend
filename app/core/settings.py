from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "t", "yes", "y", "on"}


class SessionSettings(BaseModel):
    """Runtime configuration for cookie-based sessions."""

    idle_timeout_minutes: int = Field(default=30, alias="SESSION_IDLE_TIMEOUT_MINUTES", ge=1)
    absolute_timeout_hours: int = Field(default=24, alias="SESSION_ABSOLUTE_TIMEOUT_HOURS", ge=1)
    cookie_name: str = Field(default="session_id", alias="SESSION_COOKIE_NAME")
    cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    cookie_samesite: Literal["lax", "strict", "none"] = Field(default="lax", alias="SESSION_COOKIE_SAMESITE")
    cookie_domain: Optional[str] = Field(default=None, alias="SESSION_COOKIE_DOMAIN")
    cookie_path: str = Field(default="/", alias="SESSION_COOKIE_PATH")
    cookie_max_age_seconds: Optional[int] = Field(default=None, alias="SESSION_COOKIE_MAX_AGE_SECONDS")
    send_idle_remaining_header: bool = Field(default=True, alias="SESSION_SEND_IDLE_REMAINING_HEADER")

    model_config = {"populate_by_name": True}

    @field_validator("cookie_samesite", mode="before")
    @classmethod
    def _normalize_samesite(cls, value: str) -> str:
        if value is None:
            return "lax"
        return value.lower()


@lru_cache
def get_session_settings() -> SessionSettings:
    """Load session-related configuration from environment variables."""
    return SessionSettings(
        idle_timeout_minutes=int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "30")),
        absolute_timeout_hours=int(os.getenv("SESSION_ABSOLUTE_TIMEOUT_HOURS", "24")),
        cookie_name=os.getenv("SESSION_COOKIE_NAME", "session_id"),
        cookie_secure=_as_bool(os.getenv("SESSION_COOKIE_SECURE"), default=False),
        cookie_samesite=os.getenv("SESSION_COOKIE_SAMESITE", "lax"),
        cookie_domain=os.getenv("SESSION_COOKIE_DOMAIN"),
        cookie_path=os.getenv("SESSION_COOKIE_PATH", "/"),
        cookie_max_age_seconds=(
            int(value) if (value := os.getenv("SESSION_COOKIE_MAX_AGE_SECONDS")) else None
        ),
        send_idle_remaining_header=_as_bool(os.getenv("SESSION_SEND_IDLE_REMAINING_HEADER"), default=True),
    )
