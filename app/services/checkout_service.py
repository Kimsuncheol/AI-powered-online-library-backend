from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, load_only

from app.db.session import get_session
from app.models.book import Book
from app.models.checkout import Checkout, CheckoutStatus
from app.models.member import Member, MemberRole
from app.schemas.checkout import CheckoutCreate, CheckoutUpdate

ACTIVE_STATUSES = {CheckoutStatus.CHECKED_OUT, CheckoutStatus.OVERDUE}


class CheckoutService:
    """Business logic layer for managing book checkouts."""

    DAYS_DEFAULT = 14
    MAX_EXTENSION_DAYS = 14
    MAX_RENEWALS = 2
    EXTEND_BLOCK_IF_OVERDUE = True

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _require_admin(self, actor: Member) -> None:
        if actor.role != MemberRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can perform this action.",
            )

    def _ensure_can_access(self, checkout: Checkout, actor: Member) -> None:
        if actor.role == MemberRole.ADMIN:
            return
        if checkout.member_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this checkout.",
            )

    def _normalize_datetime(self, value: datetime | date | None, _field_name: str) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def _get_member(self, member_id: str) -> Member:
        member = self.db.query(Member).filter(Member.id == member_id).first()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found.",
            )
        return member

    def _get_book(self, book_id: str) -> Book:
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )
        return book

    def _get_checkout(self, checkout_id: str, eager: bool = True) -> Checkout:
        query = self.db.query(Checkout)
        if eager:
            query = query.options(joinedload(Checkout.book), joinedload(Checkout.member))
        checkout = query.filter(Checkout.id == checkout_id).first()
        if not checkout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Checkout not found.",
            )
        return checkout

    def _ensure_book_available(self, book: Book) -> None:
        if hasattr(book, "available_copies"):
            available = getattr(book, "available_copies")
            if available is not None and available <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No available copies for this book.",
                )

    def _adjust_book_copies(self, book: Book, delta: int) -> None:
        if hasattr(book, "available_copies"):
            current = getattr(book, "available_copies", None)
            if current is None:
                return
            new_value = current + delta
            if new_value < 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient copies available for this operation.",
                )
            setattr(book, "available_copies", new_value)

    def _apply_overdue_status(self, checkouts: Iterable[Checkout]) -> None:
        now = self._now()
        changed = False
        for checkout in checkouts:
            if checkout.status == CheckoutStatus.CHECKED_OUT and checkout.due_at < now:
                checkout.status = CheckoutStatus.OVERDUE
                changed = True
        if changed:
            self.db.commit()

    # ---------------------------------------------------------------------- #
    # Public interface
    # ---------------------------------------------------------------------- #
    def create_checkout(self, payload: CheckoutCreate, actor: Member) -> Checkout:
        target_member_id = actor.id
        if payload.member_id:
            if actor.role != MemberRole.ADMIN and payload.member_id != actor.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot create checkouts for other members.",
                )
            target_member_id = payload.member_id

        member = self._get_member(target_member_id)
        book = self._get_book(payload.book_id)

        existing = (
            self.db.query(Checkout)
            .filter(
                Checkout.book_id == book.id,
                Checkout.member_id == member.id,
                Checkout.status.in_(ACTIVE_STATUSES),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Member already has an active checkout for this book.",
            )

        self._ensure_book_available(book)

        checked_out_at = self._now()
        due_at = self._normalize_datetime(payload.due_at, "dueAt")
        if due_at is None:
            due_at = checked_out_at + timedelta(days=self.DAYS_DEFAULT)

        if due_at <= checked_out_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dueAt must be later than checkedOutAt.",
            )

        checkout = Checkout(
            book_id=book.id,
            member_id=member.id,
            status=CheckoutStatus.CHECKED_OUT,
            checked_out_at=checked_out_at,
            due_at=due_at,
        )

        self._adjust_book_copies(book, -1)
        self.db.add(checkout)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to create checkout.",
            ) from exc
        self.db.refresh(checkout)
        return checkout

    def get_checkout(self, checkout_id: str, actor: Member) -> Checkout:
        checkout = self._get_checkout(checkout_id)
        self._ensure_can_access(checkout, actor)
        self._apply_overdue_status([checkout])
        self.db.refresh(checkout)
        return checkout

    def list_checkouts(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        member_id: Optional[str] = None,
        book_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        from_date: Optional[datetime | date] = None,
        to_date: Optional[datetime | date] = None,
        actor: Member,
    ) -> list[Checkout]:
        query = self.db.query(Checkout).options(
            joinedload(Checkout.book).load_only(
                Book.id,
                Book.title,
                Book.author,
                Book.cover_image_url,
                Book.isbn,
            ),
            joinedload(Checkout.member),
        )

        if actor.role != MemberRole.ADMIN:
            query = query.filter(Checkout.member_id == actor.id)
        elif member_id:
            query = query.filter(Checkout.member_id == member_id)

        if book_id:
            query = query.filter(Checkout.book_id == book_id)

        if status_filter:
            normalized = status_filter.lower()
            if normalized == "active":
                query = query.filter(Checkout.status.in_(ACTIVE_STATUSES))
            else:
                try:
                    status_enum = CheckoutStatus(normalized)
                except ValueError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid status filter.",
                    ) from exc
                query = query.filter(Checkout.status == status_enum)

        from_dt = self._normalize_datetime(from_date, "from")
        to_dt = self._normalize_datetime(to_date, "to")
        if from_dt:
            query = query.filter(Checkout.due_at >= from_dt)
        if to_dt:
            query = query.filter(Checkout.due_at <= to_dt)

        if search:
            pattern = f"%{search.lower()}%"
            query = (
                query.join(Checkout.book)
                .join(Checkout.member)
                .filter(
                    or_(
                        func.lower(Book.title).like(pattern),
                        func.lower(Book.author).like(pattern),
                        func.lower(Member.display_name).like(pattern),
                        func.lower(Member.email).like(pattern),
                    )
                )
            )

        query = query.order_by(Checkout.checked_out_at.desc())
        checkouts = query.offset(skip).limit(limit).all()
        self._apply_overdue_status(checkouts)
        return checkouts

    def update_checkout(self, checkout_id: str, payload: CheckoutUpdate, actor: Member) -> Checkout:
        checkout = self._get_checkout(checkout_id)
        self._ensure_can_access(checkout, actor)
        book = checkout.book or self._get_book(checkout.book_id)

        now = self._now()
        action = payload.action

        def _ensure_active(checkout_obj: Checkout) -> None:
            if checkout_obj.status not in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Checkout is not active.",
                )

        if action == "return":
            _ensure_active(checkout)
            checkout.status = CheckoutStatus.RETURNED
            checkout.returned_at = now
            self._adjust_book_copies(book, 1)
        elif action == "extend":
            _ensure_active(checkout)
            if self.EXTEND_BLOCK_IF_OVERDUE and checkout.status == CheckoutStatus.OVERDUE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Overdue checkouts cannot be extended.",
                )
            if checkout.due_at < now and self.EXTEND_BLOCK_IF_OVERDUE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Overdue checkouts cannot be extended.",
                )
            baseline = checkout.due_at
            if baseline < now:
                baseline = now
            if payload.days is not None:
                if payload.days > self.MAX_EXTENSION_DAYS:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Extension exceeds maximum allowed days.",
                    )
                new_due = baseline + timedelta(days=payload.days)
            else:
                new_due = self._normalize_datetime(payload.new_due_at, "newDueAt")
            if new_due is None or new_due <= baseline:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New due date must be later than the current due date.",
                )
            extension_delta = new_due - baseline
            if extension_delta > timedelta(days=self.MAX_EXTENSION_DAYS):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Extension exceeds maximum allowed days.",
                )
            total_loan_span = new_due - checkout.checked_out_at
            allowed_span = timedelta(days=self.DAYS_DEFAULT + self.MAX_EXTENSION_DAYS * self.MAX_RENEWALS)
            if total_loan_span > allowed_span:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Loan has reached the maximum number of renewals.",
                )
            checkout.due_at = new_due
            if checkout.status == CheckoutStatus.OVERDUE and new_due > now:
                checkout.status = CheckoutStatus.CHECKED_OUT
        elif action == "cancel":
            if checkout.status != CheckoutStatus.CHECKED_OUT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only pending checkouts can be cancelled.",
                )
            checkout.status = CheckoutStatus.CANCELLED
            checkout.returned_at = None
            self._adjust_book_copies(book, 1)
        elif action == "mark_lost":
            if actor.role != MemberRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only administrators can mark a checkout as lost.",
                )
            if checkout.status not in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only active checkouts can be marked as lost.",
                )
            checkout.status = CheckoutStatus.LOST
            checkout.returned_at = None
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported checkout action.",
            )

        if payload.notes is not None:
            checkout.notes = payload.notes

        self.db.commit()
        self.db.refresh(checkout)
        return checkout

    def delete_checkout(self, checkout_id: str, actor: Member) -> None:
        self._require_admin(actor)
        checkout = self._get_checkout(checkout_id, eager=False)
        book = self._get_book(checkout.book_id)

        if checkout.status in ACTIVE_STATUSES:
            self._adjust_book_copies(book, 1)

        self.db.delete(checkout)
        self.db.commit()


def get_checkout_service(db: Session = Depends(get_session)) -> CheckoutService:
    return CheckoutService(db)
