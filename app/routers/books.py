from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.models.member import Member
from app.routers.auth import get_current_member
from app.schemas.book import BookCreate, BookOut, BookUpdate
from app.services.book_service import BookService, get_book_service

router = APIRouter(prefix="/books", tags=["books"])


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
    response_model=BookOut,
)
def create_book(
    payload: BookCreate,
    current_member: Member = Depends(get_current_member),
    service: BookService = Depends(get_book_service),
) -> BookOut:
    """Create a new book entry. Admin-only."""
    book = service.create_book(payload=payload, current_member=_ensure_authenticated(current_member))
    return BookOut.model_validate(book)


@router.get(
    "/",
    response_model=list[BookOut],
)
def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1),
    service: BookService = Depends(get_book_service),
) -> list[BookOut]:
    """Return a paginated list of books with optional search."""
    books = service.list_books(skip=skip, limit=limit, search=search)
    return [BookOut.model_validate(book) for book in books]


@router.get(
    "/{book_id}",
    response_model=BookOut,
)
def get_book(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> BookOut:
    """Retrieve a single book by identifier."""
    book = service.get_book_by_id(book_id)
    return BookOut.model_validate(book)


@router.patch(
    "/{book_id}",
    response_model=BookOut,
)
def update_book(
    book_id: str,
    payload: BookUpdate,
    current_member: Member = Depends(get_current_member),
    service: BookService = Depends(get_book_service),
) -> BookOut:
    """Update an existing book. Admin-only."""
    book = service.update_book(
        book_id=book_id,
        payload=payload,
        current_member=_ensure_authenticated(current_member),
    )
    return BookOut.model_validate(book)


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_book(
    book_id: str,
    current_member: Member = Depends(get_current_member),
    service: BookService = Depends(get_book_service),
) -> Response:
    """Delete a book entry. Admin-only."""
    service.delete_book(book_id=book_id, current_member=_ensure_authenticated(current_member))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
