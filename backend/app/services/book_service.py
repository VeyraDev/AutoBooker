from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.style_types import DEFAULT_TARGET_WORDS, coerce_style
from app.models.book import Book, BookStatus
from app.models.reference import ReferenceFile
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


def _sync_discipline_field(book: Book) -> None:
    """Keep legacy discipline column in sync with disciplines[0]."""
    discs = book.disciplines if isinstance(book.disciplines, list) else None
    if discs:
        book.discipline = str(discs[0])[:100] if discs[0] else book.discipline
    elif book.discipline and not discs:
        book.disciplines = [book.discipline]


def create_book(user: User, payload: dict, db: Session) -> Book:
    data = dict(payload)
    bt = data["book_type"]
    bt_val = bt.value if hasattr(bt, "value") else str(bt)
    if data.get("target_words") is None:
        data["target_words"] = DEFAULT_TARGET_WORDS.get(bt_val, 80000)
    st = data.get("style_type")
    data["style_type"] = coerce_style(bt_val, st).value
    title = str(data.get("title") or "").strip()
    data["original_title"] = title
    data.setdefault("allow_title_optimization", False)
    discs = data.get("disciplines")
    if discs and isinstance(discs, list) and discs and not data.get("discipline"):
        data["discipline"] = str(discs[0])[:100]
    book = Book(user_id=user.id, **data)
    _sync_discipline_field(book)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def update_book(book: Book, payload: dict, db: Session) -> Book:
    for key, value in payload.items():
        if key == "style_type" and value is not None:
            value = coerce_style(book.book_type.value, value).value
        setattr(book, key, value)
    _sync_discipline_field(book)
    db.commit()
    db.refresh(book)
    return book


def delete_book(book: Book, db: Session) -> None:
    db.delete(book)
    db.commit()


def duplicate_book(source: Book, user: User, db: Session) -> Book:
    """复制书稿设定与用户资料，不复制大纲、正文、宪法与审校结果。"""
    if str(source.user_id) != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    new_title = source.title
    if not new_title.endswith("（副本）"):
        new_title = f"{new_title}（副本）"

    new_book = Book(
        user_id=user.id,
        title=new_title[:500],
        original_title=(source.original_title or source.title)[:500],
        allow_title_optimization=bool(source.allow_title_optimization),
        book_type=source.book_type,
        discipline=source.discipline,
        disciplines=source.disciplines,
        target_audience=source.target_audience,
        citation_style=source.citation_style,
        target_words=source.target_words,
        style_type=source.style_type,
        topic_tags=source.topic_tags,
        topic_brief=source.topic_brief,
        user_material=source.user_material,
        ai_inferred_settings=None,
        setup_recommendation_cache=source.setup_recommendation_cache,
        material_conflicts=source.material_conflicts,
        status=BookStatus.setup,
        ai_model=source.ai_model,
        outline_ai_model=source.outline_ai_model,
        constitution_ai_model=source.constitution_ai_model,
        writing_ai_model=source.writing_ai_model,
        last_literature_query=source.last_literature_query,
    )
    db.add(new_book)
    db.flush()

    from app.config import settings

    src_refs = db.query(ReferenceFile).filter(ReferenceFile.book_id == source.id).all()
    dest_base = settings.upload_path / str(new_book.id)
    dest_base.mkdir(parents=True, exist_ok=True)

    for ref in src_refs:
        src_path = Path(ref.storage_path)
        if not src_path.is_file():
            continue
        new_name = f"{uuid.uuid4().hex}_{Path(ref.filename).name}"
        dest_path = dest_base / new_name
        shutil.copy2(src_path, dest_path)
        db.add(
            ReferenceFile(
                book_id=new_book.id,
                filename=ref.filename,
                storage_path=str(dest_path),
                file_type=ref.file_type,
                ingest_kind=ref.ingest_kind,
                parse_status=ref.parse_status,
                error_message=ref.error_message,
                parsed_at=ref.parsed_at,
                share_to_library=ref.share_to_library,
                file_purposes=ref.file_purposes,
                outline_usage=ref.outline_usage,
                user_note=ref.user_note,
                parse_version=ref.parse_version,
                parse_artifacts=ref.parse_artifacts,
            )
        )

    db.commit()
    db.refresh(new_book)
    return new_book
