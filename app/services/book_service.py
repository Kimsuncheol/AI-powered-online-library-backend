from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.book import Book
from app.models.member import Member, MemberRole
from app.schemas.book import BookCreate, BookUpdate


class BookService:
    """Business logic layer for managing books."""

    def __init__(self, db: Session):
        self.db = db

    def _ensure_admin(self, member: Member) -> None:
        if member.role != MemberRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can perform this action.",
            )

    def _handle_integrity_error(self, exc: IntegrityError) -> None:
        self.db.rollback()
        message = str(exc.orig).lower()
        if "isbn" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A book with this ISBN already exists.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to process the book with the provided data.",
        ) from exc

    def create_book(self, payload: BookCreate, current_member: Member) -> Book:
        self._ensure_admin(current_member)

        if payload.isbn:
            existing = self.db.query(Book).filter(Book.isbn == payload.isbn).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A book with this ISBN already exists.",
                )

        book = Book(**payload.model_dump())
        self.db.add(book)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)
        self.db.refresh(book)
        return book

    def get_book_by_id(self, book_id: str) -> Book:
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )
        return book

    def list_books(self, skip: int = 0, limit: int = 20, search: Optional[str] = None) -> list[Book]:
        query = self.db.query(Book)

        if search:
            pattern = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    Book.title.ilike(pattern),
                    Book.author.ilike(pattern),
                    Book.category.ilike(pattern),
                )
            )

        return query.offset(skip).limit(limit).all()

    def update_book(self, book_id: str, payload: BookUpdate, current_member: Member) -> Book:
        self._ensure_admin(current_member)

        book = self.get_book_by_id(book_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(book, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)
        self.db.refresh(book)
        return book

    def delete_book(self, book_id: str, current_member: Member) -> None:
        self._ensure_admin(current_member)

        book = self.get_book_by_id(book_id)
        self.db.delete(book)
        self.db.commit()


def get_book_service(db: Session = Depends(get_session)) -> BookService:
    return BookService(db)
