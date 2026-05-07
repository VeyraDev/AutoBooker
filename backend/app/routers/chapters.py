"""Single chapter CRUD and SSE generation."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.agents.chapter_writer import ChapterWriterAgent
from app.agents.document_parser import DocumentParserAgent
from app.database import SessionLocal, get_db
from app.models.chapter import Chapter, ChapterStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.chapter import (
    ChapterCreateIn,
    ChapterOut,
    ChapterReorderIn,
    ChapterUpdate,
)
from app.services import book_service
from app.services.memory_service import build_book_memory, extract_chapter_memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["chapters"])


def _get_chapter(book_id: UUID, chapter_index: int, db: Session) -> Chapter:
    ch = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
        .first()
    )
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    return ch


def _chapter_payload(ch: Chapter) -> dict:
    meta = ch.content if isinstance(ch.content, dict) else {}
    return {
        "title": ch.title,
        "summary": ch.summary or "",
        "key_points": list(meta.get("key_points") or []),
        "estimated_words": int(meta.get("estimated_words") or 3000),
    }


def _chat_model_for_book(book) -> str:
    raw = (book.ai_model or "").strip()
    if settings.use_deepseek_writer():
        if raw.startswith("deepseek-"):
            return raw
        return settings.DEEPSEEK_CHAT_MODEL
    return raw or settings.CHAT_MODEL


def _memory_background(book_id: UUID, chapter_index: int, text: str) -> None:
    db = SessionLocal()
    try:
        extract_chapter_memory(book_id, chapter_index, text, db)
    except Exception:
        logger.exception("memory extract failed book=%s ch=%s", book_id, chapter_index)
    finally:
        db.close()


@router.get("/{book_id}/chapters/{chapter_index}", response_model=ChapterOut)
def get_chapter(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    return ch


@router.put("/{book_id}/chapters/{chapter_index}", response_model=ChapterOut)
def update_chapter(
    book_id: UUID,
    chapter_index: int,
    body: ChapterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    if body.title is not None:
        ch.title = body.title
    if body.summary is not None:
        ch.summary = body.summary
    if body.content is not None:
        ch.content = body.content
    db.commit()
    db.refresh(ch)
    return ch


@router.post("/{book_id}/chapters", response_model=ChapterOut, status_code=status.HTTP_201_CREATED)
def create_chapter(
    book_id: UUID,
    body: ChapterCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    max_row = db.query(func.max(Chapter.index)).filter(Chapter.book_id == book_id).scalar()
    max_idx = int(max_row or 0)

    if body.insert_at is None:
        new_index = max_idx + 1
    else:
        new_index = body.insert_at
        if new_index > max_idx + 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "insert_at cannot exceed current chapter count + 1",
            )
        to_shift = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.index >= new_index)
            .order_by(Chapter.index.desc())
            .all()
        )
        for row in to_shift:
            row.index += 1

    meta = {"key_points": [], "sections": [], "estimated_words": 3000}
    ch = Chapter(
        book_id=book.id,
        index=new_index,
        title=body.title.strip(),
        summary=body.summary,
        content=meta,
        word_count=0,
        status=ChapterStatus.pending,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.delete("/{book_id}/chapters/{chapter_index}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    db.delete(ch)
    rest = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.index > chapter_index)
        .order_by(Chapter.index.asc())
        .all()
    )
    for row in rest:
        row.index -= 1
    db.commit()
    return None


@router.patch("/{book_id}/chapters/reorder", response_model=list[ChapterOut])
def reorder_chapters(
    book_id: UUID,
    body: ChapterReorderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    all_ch = db.query(Chapter).filter(Chapter.book_id == book_id).all()
    if len(body.items) != len(all_ch):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "items must include every chapter exactly once",
        )
    id_set = {c.id for c in all_ch}
    for it in body.items:
        if it.chapter_id not in id_set:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown chapter_id")
    new_indices = sorted(it.new_index for it in body.items)
    n = len(all_ch)
    if new_indices != list(range(1, n + 1)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "new_index values must be a permutation of 1..n",
        )
    offset = 100_000
    for ch in all_ch:
        ch.index = ch.index + offset
    db.flush()
    id_to_new = {it.chapter_id: it.new_index for it in body.items}
    for ch in all_ch:
        ch.index = id_to_new[ch.id]
    db.commit()
    rows = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.index.asc()).all()
    return rows


@router.post("/{book_id}/chapters/{chapter_index}/generate")
async def generate_chapter_stream(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)

    memory = build_book_memory(book.id, chapter_index, db)
    parser = DocumentParserAgent(db, book.id)
    summary_q = (ch.summary or "") + " " + ch.title
    snippets = parser.retrieve(summary_q.strip() or book.title, top_k=4)

    chapter_dict = _chapter_payload(ch)
    writer = ChapterWriterAgent()
    chat_model = _chat_model_for_book(book)

    async def event_stream():
        row = (
            db.query(Chapter)
            .filter(Chapter.book_id == book.id, Chapter.index == chapter_index)
            .first()
        )
        if not row:
            yield f"data: {json.dumps({'error': 'chapter_not_found'}, ensure_ascii=False)}\n\n"
            return
        row.status = ChapterStatus.generating
        db.commit()
        full_text = ""
        try:
            async for token in writer.stream(
                chapter_dict, memory, snippets, model=chat_model
            ):
                full_text += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            row = (
                db.query(Chapter)
                .filter(Chapter.book_id == book.id, Chapter.index == chapter_index)
                .first()
            )
            if row:
                meta = dict(row.content) if isinstance(row.content, dict) else {}
                meta["text"] = full_text
                row.content = meta
                row.word_count = len(full_text)
                row.status = ChapterStatus.done
                db.commit()
            asyncio.create_task(asyncio.to_thread(_memory_background, book.id, chapter_index, full_text))
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("chapter generate failed")
            row = (
                db.query(Chapter)
                .filter(Chapter.book_id == book.id, Chapter.index == chapter_index)
                .first()
            )
            if row:
                row.status = ChapterStatus.pending
                db.commit()
            yield f"data: {json.dumps({'error': 'generation_failed'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
