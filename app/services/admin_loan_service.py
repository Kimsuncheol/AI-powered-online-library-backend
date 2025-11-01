from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_session
from app.models.book import Book
from app.models.checkout import Checkout, CheckoutStatus
from app.models.member import Member, MemberRole
from app.schemas.checkout import CheckoutCreate, CheckoutUpdate
from app.services.checkout_service import ACTIVE_STATUSES


class AdminLoanService:
    """Business logic for administrator-controlled loan (checkout) management."""

    DAYS_DEFAULT = 14

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _require_admin(self, actor: Member | None) -> Member:
        if actor is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )
        if actor.role != MemberRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator privileges required.",
            )
        return actor

    def _normalize_datetime(self, value: datetime | date | None) -> Optional[datetime]:
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
            query = query.options(
                joinedload(Checkout.book).load_only(
                    Book.id,
                    Book.title,
                    Book.author,
                    Book.cover_image_url,
                    Book.isbn,
                ),
                joinedload(Checkout.member).load_only(
                    Member.id,
                    Member.email,
                    Member.display_name,
                    Member.avatar_url,
                ),
            )
        checkout = query.filter(Checkout.id == checkout_id).first()
        if not checkout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Checkout not found.",
            )
        return checkout

    def _ensure_book_available(self, book: Book) -> None:
        if hasattr(book, "available_copies"):
            available = getattr(book, "available_copies", None)
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

    def _apply_overdue_status(self, checkouts: list[Checkout]) -> None:
        now = self._now()
        mutated = False
        for checkout in checkouts:
            if checkout.status == CheckoutStatus.CHECKED_OUT and checkout.due_at < now:
                checkout.status = CheckoutStatus.OVERDUE
                mutated = True
        if mutated:
            self.db.commit()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def list_loans(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        member_id: Optional[str] = None,
        book_id: Optional[str] = None,
        from_date: Optional[datetime | date] = None,
        to_date: Optional[datetime | date] = None,
        actor: Member | None,
    ) -> list[Checkout]:
        self._require_admin(actor)

        query = self.db.query(Checkout).options(
            joinedload(Checkout.book).load_only(
                Book.id,
                Book.title,
                Book.author,
                Book.cover_image_url,
                Book.isbn,
            ),
            joinedload(Checkout.member).load_only(
                Member.id,
                Member.email,
                Member.display_name,
                Member.avatar_url,
            ),
        )

        if member_id:
            query = query.filter(Checkout.member_id == member_id)

        if book_id:
            query = query.filter(Checkout.book_id == book_id)

        if status_filter:
            normalized = status_filter.lower()
            if normalized != "all":
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

        from_dt = self._normalize_datetime(from_date)
        to_dt = self._normalize_datetime(to_date)
        if from_dt:
            query = query.filter(Checkout.due_at >= from_dt)
        if to_dt:
            query = query.filter(Checkout.due_at <= to_dt)

        if search:
            trimmed = search.strip()
            if trimmed:
                pattern = f"%{trimmed}%"
                query = (
                    query.join(Checkout.book)
                    .join(Checkout.member)
                    .filter(
                        or_(
                            Book.title.ilike(pattern),
                            Book.author.ilike(pattern),
                            Member.display_name.ilike(pattern),
                            Member.email.ilike(pattern),
                        )
                    )
                )

        query = query.order_by(Checkout.checked_out_at.desc())
        checkouts = query.offset(skip).limit(limit).all()
        if checkouts:
            self._apply_overdue_status(checkouts)
            for checkout in checkouts:
                # ensure refreshed state after potential status updates
                self.db.refresh(checkout)
        return checkouts

    def get_loan(self, checkout_id: str, *, actor: Member | None) -> Checkout:
        self._require_admin(actor)
        checkout = self._get_checkout(checkout_id)
        self._apply_overdue_status([checkout])
        self.db.refresh(checkout)
        return checkout

    def create_loan(self, payload: CheckoutCreate, *, actor: Member | None) -> Checkout:
        admin = self._require_admin(actor)

        target_member_id = payload.member_id or admin.id
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
        due_at = self._normalize_datetime(payload.due_at)
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
        return self._get_checkout(checkout.id)

    def update_loan(self, checkout_id: str, payload: CheckoutUpdate, *, actor: Member | None) -> Checkout:
        self._require_admin(actor)
        checkout = self._get_checkout(checkout_id)
        book = checkout.book or self._get_book(checkout.book_id)
        now = self._now()
        action = payload.action

        if action == "return":
            if checkout.status not in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only active loans can be returned.",
                )
            checkout.status = CheckoutStatus.RETURNED
            checkout.returned_at = now
            self._adjust_book_copies(book, 1)
        elif action == "extend":
            if checkout.status not in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only active loans can be extended.",
                )
            baseline = checkout.due_at
            if baseline < now:
                baseline = now
            if payload.days is not None:
                new_due = baseline + timedelta(days=payload.days)
            else:
                new_due = self._normalize_datetime(payload.new_due_at)
            if new_due is None or new_due <= baseline:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New due date must be later than the current due date.",
                )
            checkout.due_at = new_due
            if checkout.status == CheckoutStatus.OVERDUE and new_due > now:
                checkout.status = CheckoutStatus.CHECKED_OUT
        elif action == "cancel":
            if checkout.status not in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only active loans can be cancelled.",
                )
            checkout.status = CheckoutStatus.CANCELLED
            checkout.returned_at = None
            self._adjust_book_copies(book, 1)
        elif action == "mark_lost":
            if checkout.status not in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only active loans can be marked as lost.",
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

    def delete_loan(self, checkout_id: str, *, actor: Member | None) -> None:
        self._require_admin(actor)
        checkout = self._get_checkout(checkout_id, eager=False)

        if checkout.status in ACTIVE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active loans cannot be deleted. Return, cancel, or mark lost first.",
            )

        self.db.delete(checkout)
        self.db.commit()


def get_admin_loan_service(db: Session = Depends(get_session)) -> AdminLoanService:
    return AdminLoanService(db=db)
