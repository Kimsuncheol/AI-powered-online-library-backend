from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.models.member import Member, MemberRole
from app.routers.auth import get_current_member
from app.schemas.member import MemberCreate, MemberOut, MemberUpdate
from app.services.member_admin_service import (
    MemberAdminService,
    get_member_admin_service,
)

router = APIRouter(prefix="/admin/members", tags=["admin", "members"])


def _ensure_admin(current_member: Member) -> None:
    if current_member.role != MemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Administrator privileges required."},
        )


@router.get("", response_model=list[MemberOut])
def list_members(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1),
    search: Optional[str] = Query(default=None),
    current_member: Member = Depends(get_current_member),
    service: MemberAdminService = Depends(get_member_admin_service),
) -> list[MemberOut]:
    _ensure_admin(current_member)
    return service.list_members(skip=skip, limit=limit, search=search)


@router.get("/{member_id}", response_model=MemberOut)
def get_member(
    member_id: str,
    current_member: Member = Depends(get_current_member),
    service: MemberAdminService = Depends(get_member_admin_service),
) -> MemberOut:
    _ensure_admin(current_member)
    return service.get_member_by_id(member_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MemberOut)
def create_member(
    payload: MemberCreate,
    current_member: Member = Depends(get_current_member),
    service: MemberAdminService = Depends(get_member_admin_service),
) -> MemberOut:
    _ensure_admin(current_member)
    return service.create_member(payload)


@router.patch("/{member_id}", response_model=MemberOut)
def update_member(
    member_id: str,
    payload: MemberUpdate,
    current_member: Member = Depends(get_current_member),
    service: MemberAdminService = Depends(get_member_admin_service),
) -> MemberOut:
    _ensure_admin(current_member)
    return service.update_member(member_id=member_id, payload=payload)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_member(
    member_id: str,
    current_member: Member = Depends(get_current_member),
    service: MemberAdminService = Depends(get_member_admin_service),
) -> Response:
    _ensure_admin(current_member)
    service.delete_member(member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
