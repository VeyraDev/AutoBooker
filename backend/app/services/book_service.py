from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.user import User


def get_book_or_404(book_id: UUID, user: User, db: Session) -> Book:
    """Fetch a book and enforce owner check; raises 404 / 403."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    if str(book.user_id) != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return book


def list_user_books(user: User, db: Session) -> list[Book]:
    return (
        db.query(Book)
        .filter(Book.user_id == user.id)
        .order_by(Book.created_at.desc())
        .all()
    )


def create_book(user: User, payload: dict, db: Session) -> Book:
    book = Book(user_id=user.id, **payload)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def update_book(book: Book, payload: dict, db: Session) -> Book:
    for key, value in payload.items():
        setattr(book, key, value)
    db.commit()
    db.refresh(book)
    return book


def delete_book(book: Book, db: Session) -> None:
    db.delete(book)
    db.commit()
