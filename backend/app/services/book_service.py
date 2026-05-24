from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.style_types import DEFAULT_TARGET_WORDS, coerce_style
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
    data = dict(payload)
    bt = data["book_type"]
    bt_val = bt.value if hasattr(bt, "value") else str(bt)
    if data.get("target_words") is None:
        data["target_words"] = DEFAULT_TARGET_WORDS.get(bt_val, 80000)
    st = data.get("style_type")
    data["style_type"] = coerce_style(bt_val, st).value
    book = Book(user_id=user.id, **data)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def update_book(book: Book, payload: dict, db: Session) -> Book:
    for key, value in payload.items():
        if key == "style_type" and value is not None:
            value = coerce_style(book.book_type.value, value).value
        setattr(book, key, value)
    db.commit()
    db.refresh(book)
    return book


def delete_book(book: Book, db: Session) -> None:
    db.delete(book)
    db.commit()
