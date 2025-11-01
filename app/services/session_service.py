from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
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
        attempts = 0
        while True:
            attempts += 1
            session = SessionModel(
                member_id=member.id,
                user_agent=user_agent,
                ip_addr=ip_addr,
                created_at=now,
                last_active_at=now,
            )
            try:
                with self.db.begin():
                    (
                        self.db.query(SessionModel)
                        .filter(SessionModel.member_id == member.id, SessionModel.revoked.is_(False))
                        .update(
                            {"revoked": True, "revoked_at": now},
                            synchronize_session=False,
                        )
                    )
                    self.db.add(session)
                    self.db.flush()
            except IntegrityError:
                self.db.rollback()
                if attempts >= 2:
                    raise
                continue
            else:
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
        now = datetime.now(timezone.utc)
        updated = (
            self.db.query(SessionModel)
            .filter(SessionModel.member_id == member_id, SessionModel.revoked.is_(False))
            .update({"revoked": True, "revoked_at": now}, synchronize_session=False)
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
            if session.revoked_at is None:
                session.revoked_at = datetime.now(timezone.utc)
                self.db.add(session)
                self.db.commit()
            return
        now = datetime.now(timezone.utc)
        session.revoked = True
        session.revoked_at = now
        self.db.add(session)
        self.db.commit()


def get_session_service(
    db: SASession = Depends(get_session),
    settings: SessionSettings = Depends(get_session_settings),
) -> SessionService:
    return SessionService(db=db, settings=settings)
