from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel, Field


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class JWTSettings(BaseModel):
    secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_exp_minutes: int = Field(default=15, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_exp_minutes: int = Field(default=60 * 24 * 7, alias="JWT_REFRESH_TOKEN_EXPIRE_MINUTES")
    issuer: Optional[str] = Field(default="auth-service", alias="JWT_ISSUER")
    audience: Optional[str] = Field(default=None, alias="JWT_AUDIENCE")

    @property
    def access_token_expires_delta(self) -> timedelta:
        return timedelta(minutes=self.access_token_exp_minutes)

    @property
    def refresh_token_expires_delta(self) -> timedelta:
        return timedelta(minutes=self.refresh_token_exp_minutes)

    model_config = {"populate_by_name": True}


class TokenPayload(BaseModel):
    subject: str = Field(alias="sub")
    role: str
    token_type: TokenType = Field(alias="type")
    issued_at: Optional[int] = Field(default=None, alias="iat")
    expires_at: int = Field(alias="exp")
    issuer: Optional[str] = Field(default=None, alias="iss")
    audience: Optional[str] = Field(default=None, alias="aud")

    model_config = {"populate_by_name": True}


@dataclass
class EncodedTokens:
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or validated."""


@lru_cache
def get_jwt_settings() -> JWTSettings:
    """Load JWT configuration from environment variables."""
    return JWTSettings(
        secret_key=os.getenv("JWT_SECRET_KEY", "change-me"),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_exp_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
        refresh_token_exp_minutes=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 14))),
        issuer=os.getenv("JWT_ISSUER", "auth-service"),
        audience=os.getenv("JWT_AUDIENCE"),
    )


def create_access_token(*, subject: str, role: str, settings: JWTSettings) -> str:
    """Generate an encoded access token."""
    return _create_token(
        token_type=TokenType.ACCESS,
        subject=subject,
        role=role,
        settings=settings,
        expires_delta=settings.access_token_expires_delta,
    )


def create_refresh_token(*, subject: str, role: str, settings: JWTSettings) -> str:
    """Generate an encoded refresh token."""
    return _create_token(
        token_type=TokenType.REFRESH,
        subject=subject,
        role=role,
        settings=settings,
        expires_delta=settings.refresh_token_expires_delta,
    )


def decode_token(token: str, settings: JWTSettings) -> TokenPayload:
    """Decode and validate an encoded JWT."""
    decode_kwargs = {
        "algorithms": [settings.algorithm],
        "options": {"verify_aud": settings.audience is not None},
    }
    if settings.audience:
        decode_kwargs["audience"] = settings.audience
    if settings.issuer:
        decode_kwargs["issuer"] = settings.issuer

    try:
        payload = jwt.decode(token, settings.secret_key, **decode_kwargs)
    except JWTError as exc:  # pragma: no cover - jose already well-tested
        raise InvalidTokenError(str(exc)) from exc

    return TokenPayload.model_validate(payload)


def _create_token(
    *,
    token_type: TokenType,
    subject: str,
    role: str,
    settings: JWTSettings,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    expiration = now + expires_delta
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
    }
    if settings.issuer:
        payload["iss"] = settings.issuer
    if settings.audience:
        payload["aud"] = settings.audience

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

