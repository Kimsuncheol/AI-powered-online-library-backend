from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, Response, status

from app.core.settings import SessionSettings, get_session_settings
from app.models.member import Member
from app.models.session import Session as SessionModel
from app.services.session_service import SessionService, get_session_service


def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def require_session(
    request: Request,
    response: Response,
    session_service: SessionService = Depends(get_session_service),
    settings: SessionSettings = Depends(get_session_settings),
) -> Member:
    sid = request.cookies.get(settings.cookie_name)
    if not sid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Session cookie is required."},
        )

    session: SessionModel | None = session_service.get_active_session(sid)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_session", "message": "Session is invalid or expired."},
        )

    now = datetime.now(timezone.utc)
    idle_timeout = session_service.idle_timeout
    absolute_timeout = session_service.absolute_timeout
    created_at = _coerce_utc(session.created_at)
    last_active_at = _coerce_utc(session.last_active_at)

    if now - created_at > absolute_timeout:
        session_service.mark_revoked(session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "absolute_expired", "message": "Session expired. Please sign in again."},
        )

    idle_elapsed = now - last_active_at
    if idle_elapsed > idle_timeout:
        session_service.mark_revoked(session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "idle_expired", "message": "Session expired due to inactivity."},
        )

    if settings.send_idle_remaining_header:
        remaining = max(0, int((idle_timeout - idle_elapsed).total_seconds()))
        response.headers["X-Session-Idle-Remaining"] = str(remaining)

    session_service.slide_session(session, timestamp=now)
    return session.member
