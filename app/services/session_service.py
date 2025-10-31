from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session as SASession

from app.core.settings import SessionSettings, get_session_settings
from app.db.session import get_session
from app.models.member import Member
from app.models.session import Session as SessionModel


class SessionService:
    """Encapsulates persistence and lifecycle operations for member sessions."""

    def __init__(self, db: SASession, settings: SessionSettings) -> None:
        self.db = db
        self.settings = settings

    def create_session(
        self,
        *,
        member: Member,
        user_agent: Optional[str],
        ip_addr: Optional[str],
    ) -> SessionModel:
        now = datetime.now(timezone.utc)
        session = SessionModel(
            member_id=member.id,
            user_agent=user_agent,
            ip_addr=ip_addr,
            created_at=now,
            last_active_at=now,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_active_session(self, session_id: str) -> Optional[SessionModel]:
        session = self.db.get(SessionModel, session_id)
        if not session or session.revoked:
            return None
        return session

    def revoke_session(self, session_id: str) -> bool:
        session = self.db.get(SessionModel, session_id)
        if not session:
            return False
        self.mark_revoked(session)
        return True

    def revoke_all_for_member(self, member_id: str) -> int:
        updated = (
            self.db.query(SessionModel)
            .filter(SessionModel.member_id == member_id, SessionModel.revoked.is_(False))
            .update({"revoked": True})
        )
        if updated:
            self.db.commit()
        return updated or 0

    @property
    def idle_timeout(self) -> timedelta:
        return timedelta(minutes=self.settings.idle_timeout_minutes)

    @property
    def absolute_timeout(self) -> timedelta:
        return timedelta(hours=self.settings.absolute_timeout_hours)

    def slide_session(self, session: SessionModel, *, timestamp: datetime) -> None:
        session.last_active_at = timestamp
        self.db.add(session)
        self.db.commit()

    def mark_revoked(self, session: SessionModel) -> None:
        if session.revoked:
            return
        session.revoked = True
        self.db.add(session)
        self.db.commit()


def get_session_service(
    db: SASession = Depends(get_session),
    settings: SessionSettings = Depends(get_session_settings),
) -> SessionService:
    return SessionService(db=db, settings=settings)
