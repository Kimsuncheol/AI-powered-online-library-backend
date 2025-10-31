from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.member import Member
from app.schemas.member import MemberOut, MemberUpdate


def get_profile(db: Session, member_id: str) -> MemberOut:
    """Return the profile of the given member."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    return MemberOut.model_validate(member)


def update_profile(db: Session, member_id: str, payload: MemberUpdate) -> MemberOut:
    """Update profile fields for the given member."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)

    db.commit()
    db.refresh(member)
    return MemberOut.model_validate(member)


def delete_profile(db: Session, member_id: str) -> None:
    """Delete the member’s profile and account."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    db.delete(member)
    db.commit()
