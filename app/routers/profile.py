from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.member import Member
from app.routers.auth import get_current_member
from app.schemas.member import MemberOut, MemberUpdate
from app.services.profile_service import delete_profile, get_profile, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=MemberOut)
def read_profile(
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_session),
) -> MemberOut:
    """Return the authenticated member's profile."""
    return get_profile(db=db, member_id=current_member.id)


@router.patch("/me", response_model=MemberOut)
def update_profile_me(
    payload: MemberUpdate,
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_session),
) -> MemberOut:
    """Update profile details for the authenticated member."""
    return update_profile(db=db, member_id=current_member.id, payload=payload)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_profile_me(
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_session),
) -> Response:
    """Delete the authenticated member's account."""
    delete_profile(db=db, member_id=current_member.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
