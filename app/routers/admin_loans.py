from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.models.member import Member, MemberRole
from app.routers.auth import get_current_member
from app.schemas.checkout import CheckoutCreate, CheckoutOut, CheckoutUpdate
from app.services.admin_loan_service import AdminLoanService, get_admin_loan_service

router = APIRouter(prefix="/admin/loans", tags=["admin", "loans"])


def _require_admin(member: Member | None) -> Member:
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    if member.role != MemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )
    return member


@router.get("/", response_model=list[CheckoutOut])
def list_loans(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(default=None, min_length=1),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    member_id: Optional[str] = Query(default=None, alias="memberId"),
    book_id: Optional[str] = Query(default=None, alias="bookId"),
    from_param: Optional[datetime | date] = Query(default=None, alias="from"),
    to_param: Optional[datetime | date] = Query(default=None, alias="to"),
    current_member: Member = Depends(get_current_member),
    service: AdminLoanService = Depends(get_admin_loan_service),
) -> list[CheckoutOut]:
    admin = _require_admin(current_member)
    checkouts = service.list_loans(
        skip=skip,
        limit=limit,
        search=search,
        status_filter=status_filter,
        member_id=member_id,
        book_id=book_id,
        from_date=from_param,
        to_date=to_param,
        actor=admin,
    )
    return [CheckoutOut.model_validate(checkout) for checkout in checkouts]


@router.get("/{checkout_id}", response_model=CheckoutOut)
def get_loan(
    checkout_id: str,
    current_member: Member = Depends(get_current_member),
    service: AdminLoanService = Depends(get_admin_loan_service),
) -> CheckoutOut:
    admin = _require_admin(current_member)
    checkout = service.get_loan(checkout_id=checkout_id, actor=admin)
    return CheckoutOut.model_validate(checkout)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CheckoutOut)
def create_loan(
    payload: CheckoutCreate,
    current_member: Member = Depends(get_current_member),
    service: AdminLoanService = Depends(get_admin_loan_service),
) -> CheckoutOut:
    admin = _require_admin(current_member)
    checkout = service.create_loan(payload=payload, actor=admin)
    return CheckoutOut.model_validate(checkout)


@router.patch("/{checkout_id}", response_model=CheckoutOut)
def update_loan(
    checkout_id: str,
    payload: CheckoutUpdate,
    current_member: Member = Depends(get_current_member),
    service: AdminLoanService = Depends(get_admin_loan_service),
) -> CheckoutOut:
    admin = _require_admin(current_member)
    checkout = service.update_loan(checkout_id=checkout_id, payload=payload, actor=admin)
    return CheckoutOut.model_validate(checkout)


@router.delete("/{checkout_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_loan(
    checkout_id: str,
    current_member: Member = Depends(get_current_member),
    service: AdminLoanService = Depends(get_admin_loan_service),
) -> Response:
    admin = _require_admin(current_member)
    service.delete_loan(checkout_id=checkout_id, actor=admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
