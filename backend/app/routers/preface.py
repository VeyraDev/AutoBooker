"""Book preface CRUD and SSE generation."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.preface_writer import PrefaceWriterAgent
from app.database import get_db
from app.llm.providers import resolve_book_writing_model
from app.models.book import Book
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.preface import PrefaceOut, PrefacePut
from app.services import book_service
from app.services.markdown_to_tiptap import markdown_body_to_tiptap_blocks
from app.services.preface_service import get_preface, set_preface

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["preface"])


def _to_out(book) -> PrefaceOut:
    return PrefaceOut.model_validate(get_preface(book))


def _live_book(db: Session, book_id: UUID, fallback: Book) -> Book:
    return db.get(Book, book_id) or fallback


def _persist_preface_body(db: Session, book: Book, full: str, *, status: str = "done") -> None:
    blocks = markdown_body_to_tiptap_blocks(full)
    doc = {"type": "doc", "content": blocks}
    wc = len(full.replace("\n", "").replace(" ", ""))
    set_preface(
        book,
        {
            "status": status,
            "tiptap_json": doc,
            "word_count": wc,
            "text": full,
            "summary": full[:500],
        },
    )
    db.commit()


@router.get("/{book_id}/preface", response_model=PrefaceOut)
def get_book_preface(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    return _to_out(book)


@router.put("/{book_id}/preface", response_model=PrefaceOut)
def put_book_preface(
    book_id: UUID,
    body: PrefacePut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    patch = body.model_dump(exclude_unset=True)
    set_preface(book, patch)
    db.commit()
    db.refresh(book)
    return _to_out(book)


@router.post("/{book_id}/preface/generate")
async def generate_preface_stream(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    pf = get_preface(book)
    if not pf.get("enabled", True):
        raise HTTPException(400, "本书未启用前言")

    writer = PrefaceWriterAgent()
    model = resolve_book_writing_model(book, user, db)
    target_words = int(pf.get("target_words") or 3000)

    async def event_stream():
        full = ""
        try:
            live = _live_book(db, book_id, book)
            set_preface(live, {"status": "generating"})
            db.commit()
            narrative = live.narrative_constitution or ""
            async for token in writer.stream(
                book_title=live.title or "",
                brief=str(pf.get("brief") or ""),
                narrative_constitution=narrative,
                target_words=target_words,
                book_type=live.book_type.value,
                model=model,
            ):
                full += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            live = _live_book(db, book_id, book)
            _persist_preface_body(db, live, full, status="done")
            yield f"data: {json.dumps({'done': True, 'markdown': full}, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("preface generate failed")
            if full.strip():
                try:
                    live = _live_book(db, book_id, book)
                    _persist_preface_body(db, live, full, status="done")
                    yield f"data: {json.dumps({'done': True, 'markdown': full, 'partial': True}, ensure_ascii=False)}\n\n"
                    return
                except Exception:
                    logger.exception("preface partial save failed")
            live = _live_book(db, book_id, book)
            set_preface(live, {"status": "empty"})
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
