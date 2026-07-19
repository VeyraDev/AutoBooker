from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.style_types import DEFAULT_TARGET_WORDS, coerce_style
from app.models.book import Book, BookStatus, CitationStyle
from app.models.chapter import Chapter, ChapterStatus
from app.models.reference import ReferenceFile
from app.models.user import User
from app.services.heading_formatter import normalize_outline_sections
from app.services.preface_service import DEFAULT_PREFACE, get_preface


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


def allocate_default_book_title(user_id: UUID, db: Session) -> str:
    for i in range(1, 10_000):
        candidate = f"书稿{i}"
        exists = (
            db.query(Book.id)
            .filter(Book.user_id == user_id, Book.title == candidate)
            .first()
        )
        if not exists:
            return candidate
    return f"书稿{uuid.uuid4().hex[:6]}"


def create_book(
    user: User,
    payload: dict,
    db: Session,
    *,
    commit: bool = True,
) -> Book:
    data = dict(payload)
    bt = data["book_type"]
    bt_val = bt.value if hasattr(bt, "value") else str(bt)
    if data.get("target_words") is None:
        data["target_words"] = DEFAULT_TARGET_WORDS.get(bt_val, 80000)
    st = data.get("style_type")
    data["style_type"] = coerce_style(bt_val, st).value
    title = str(data.get("title") or "").strip()
    if not title:
        title = allocate_default_book_title(user.id, db)
    data["title"] = title
    data["original_title"] = title
    data.setdefault("allow_title_optimization", False)
    discs = data.get("disciplines")
    if discs and isinstance(discs, list) and discs and not data.get("discipline"):
        data["discipline"] = str(discs[0])[:100]
    book = Book(user_id=user.id, **data)
    _sync_discipline_field(book)
    db.add(book)
    if commit:
        db.commit()
        db.refresh(book)
    else:
        db.flush()
    return book


def update_book(book: Book, payload: dict, db: Session) -> Book:
    previous_citation_style = book.citation_style
    for key, value in payload.items():
        if key == "style_type" and value is not None:
            value = coerce_style(book.book_type.value, value).value
        elif key == "citation_style" and value is not None:
            value = CitationStyle(value)
        elif key == "status" and value is not None:
            value = BookStatus(value)
        elif key == "publication_info" and value is not None:
            from app.services.publication.publication_info import normalize_publication_info

            value = normalize_publication_info(
                value if isinstance(value, dict) else None,
                fallback_title=book.title,
            )
        setattr(book, key, value)
    _sync_discipline_field(book)
    if "citation_style" in payload and book.citation_style != previous_citation_style:
        from app.services.citation_nodes import refresh_book_citation_rendering
        from app.services.citation_service import sync_book_bibliography

        db.flush()
        refresh_book_citation_rendering(db, book)
        sync_book_bibliography(db, book)
    db.commit()
    db.refresh(book)
    return book


def delete_book(book: Book, db: Session) -> None:
    db.delete(book)
    db.commit()


def _outline_meta_from_chapter_content(meta: object) -> dict:
    raw = meta if isinstance(meta, dict) else {}
    sections_raw = raw.get("sections") or []
    sections = (
        normalize_outline_sections([s for s in sections_raw if isinstance(s, dict)])
        if isinstance(sections_raw, list)
        else []
    )
    return {
        "key_points": list(raw.get("key_points") or []),
        "sections": sections,
        "estimated_words": int(raw.get("estimated_words") or 3000),
    }


def _preface_outline_from_source(source: Book) -> dict | None:
    pf = get_preface(source)
    brief = str(pf.get("brief") or "").strip()
    summary = str(pf.get("summary") or "").strip()
    if not brief and not summary:
        return None
    return {
        **DEFAULT_PREFACE,
        "enabled": bool(pf.get("enabled", True)),
        "target_words": int(pf.get("target_words") or 3000),
        "brief": pf.get("brief", ""),
        "summary": pf.get("summary", ""),
        "text": "",
        "word_count": 0,
        "tiptap_json": None,
        "status": "ready" if brief else "empty",
    }


def _duplicate_result_message(*, copy_outline: bool, copied_chapters: int) -> str:
    if copy_outline and copied_chapters > 0:
        return "已基于原书创建新书，设定、用户资料与大纲已复制，正文与审校结果未复制。"
    if copy_outline:
        return "已基于原书创建新书，设定与用户资料已复制（原书尚无大纲可复用）。"
    return "已基于原书创建新书，设定与用户资料已复制，大纲与正文未复制。"


def duplicate_book(
    source: Book,
    user: User,
    db: Session,
    *,
    copy_outline: bool = False,
) -> tuple[Book, str]:
    """复制书稿设定与用户资料；可选复制大纲结构，不复制正文、宪法与审校结果。"""
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
        last_literature_query=source.last_literature_query,
    )
    db.add(new_book)
    db.flush()

    src_refs = db.query(ReferenceFile).filter(ReferenceFile.book_id == source.id).all()

    for ref in src_refs:
        new_ref = ReferenceFile(
            book_id=new_book.id,
            filename=ref.filename,
            storage_path=ref.storage_path,
            asset_id=ref.asset_id,
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
        if ref.asset_id:
            from app.models.binary_asset import BinaryAsset, AssetDomain, AssetRole

            old_asset = db.query(BinaryAsset).filter(BinaryAsset.id == ref.asset_id).first()
            if old_asset:
                copied = BinaryAsset(
                    book_id=new_book.id,
                    owner_user_id=user.id,
                    asset_domain=AssetDomain.reference,
                    asset_role=AssetRole.original_upload,
                    filename=old_asset.filename,
                    mime_type=old_asset.mime_type,
                    extension=old_asset.extension,
                    content=old_asset.content,
                    size_bytes=old_asset.size_bytes,
                    sha256=old_asset.sha256,
                    width=old_asset.width,
                    height=old_asset.height,
                    metadata_json=old_asset.metadata_json,
                )
                db.add(copied)
                db.flush()
                new_ref.asset_id = copied.id
                new_ref.storage_path = f"db://binary_assets/{copied.id}"
        elif ref.storage_path:
            src_path = Path(ref.storage_path)
            if src_path.is_file():
                from app.services.assets.reference_asset_service import ReferenceAssetService

                content = src_path.read_bytes()
                new_ref.storage_path = None
                db.add(new_ref)
                db.flush()
                ReferenceAssetService(db).attach_upload(ref=new_ref, content=content, owner_user_id=user.id)
                continue
        db.add(new_ref)

    copied_chapters = 0
    if copy_outline:
        src_chapters = (
            db.query(Chapter)
            .filter(Chapter.book_id == source.id)
            .order_by(Chapter.index.asc())
            .all()
        )
        for ch in src_chapters:
            db.add(
                Chapter(
                    book_id=new_book.id,
                    index=ch.index,
                    title=ch.title,
                    summary=ch.summary,
                    content=_outline_meta_from_chapter_content(ch.content),
                    word_count=0,
                    status=ChapterStatus.pending,
                )
            )
        copied_chapters = len(src_chapters)
        if copied_chapters > 0:
            new_book.status = BookStatus.outline_ready
            new_book.constitution_stale = True
        preface_outline = _preface_outline_from_source(source)
        if preface_outline is not None:
            new_book.preface = preface_outline

    db.commit()
    db.refresh(new_book)
    return new_book, _duplicate_result_message(
        copy_outline=copy_outline,
        copied_chapters=copied_chapters,
    )
