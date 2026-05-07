import re
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.book import BookCreate, BookOut, BookUpdate
from app.services import book_service, export_service

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookOut])
def list_books(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return book_service.list_user_books(user, db)


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(
    body: BookCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return book_service.create_book(user, body.model_dump(exclude_unset=False), db)


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return book_service.get_book_or_404(book_id, user, db)


@router.put("/{book_id}", response_model=BookOut)
def update_book(
    book_id: UUID,
    body: BookUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    return book_service.update_book(book, body.model_dump(exclude_unset=True), db)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    book_service.delete_book(book, db)
    return None


@router.get("/{book_id}/export")
def export_book(
    book_id: UUID,
    format: str = Query(
        "markdown",
        description="导出格式：markdown / md / docx",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body, filename, media_type = export_service.export_book_bytes(book_id, format, user, db)
    ascii_name = re.sub(r'[^\x20-\x7E]', "_", filename) or "export"
    cd = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(content=body, media_type=media_type, headers={"Content-Disposition": cd})
