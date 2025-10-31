from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.models.member import Member
from app.routers.auth import get_current_member
from app.schemas.checkout import CheckoutCreate, CheckoutOut, CheckoutUpdate
from app.services.checkout_service import CheckoutService, get_checkout_service

router = APIRouter(prefix="/checkouts", tags=["checkouts"])


def _ensure_authenticated(member: Member | None) -> Member:
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return member


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=CheckoutOut,
)
def create_checkout(
    payload: CheckoutCreate,
    current_member: Member = Depends(get_current_member),
    service: CheckoutService = Depends(get_checkout_service),
) -> CheckoutOut:
    checkout = service.create_checkout(payload=payload, actor=_ensure_authenticated(current_member))
    return CheckoutOut.model_validate(checkout)


@router.get(
    "/",
    response_model=list[CheckoutOut],
)
def list_checkouts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(default=None, min_length=1),
    member_id: Optional[str] = Query(default=None, alias="memberId"),
    book_id: Optional[str] = Query(default=None, alias="bookId"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    from_param: Optional[datetime | date] = Query(default=None, alias="from"),
    to_param: Optional[datetime | date] = Query(default=None, alias="to"),
    current_member: Member = Depends(get_current_member),
    service: CheckoutService = Depends(get_checkout_service),
) -> list[CheckoutOut]:
    checkouts = service.list_checkouts(
        skip=skip,
        limit=limit,
        search=search,
        member_id=member_id,
        book_id=book_id,
        status_filter=status_filter,
        from_date=from_param,
        to_date=to_param,
        actor=_ensure_authenticated(current_member),
    )
    return [CheckoutOut.model_validate(checkout) for checkout in checkouts]


@router.get(
    "/{checkout_id}",
    response_model=CheckoutOut,
)
def get_checkout(
    checkout_id: str,
    current_member: Member = Depends(get_current_member),
    service: CheckoutService = Depends(get_checkout_service),
) -> CheckoutOut:
    checkout = service.get_checkout(checkout_id=checkout_id, actor=_ensure_authenticated(current_member))
    return CheckoutOut.model_validate(checkout)


@router.patch(
    "/{checkout_id}",
    response_model=CheckoutOut,
)
def update_checkout(
    checkout_id: str,
    payload: CheckoutUpdate,
    current_member: Member = Depends(get_current_member),
    service: CheckoutService = Depends(get_checkout_service),
) -> CheckoutOut:
    checkout = service.update_checkout(
        checkout_id=checkout_id,
        payload=payload,
        actor=_ensure_authenticated(current_member),
    )
    return CheckoutOut.model_validate(checkout)


@router.delete(
    "/{checkout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_checkout(
    checkout_id: str,
    current_member: Member = Depends(get_current_member),
    service: CheckoutService = Depends(get_checkout_service),
) -> Response:
    service.delete_checkout(checkout_id=checkout_id, actor=_ensure_authenticated(current_member))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
