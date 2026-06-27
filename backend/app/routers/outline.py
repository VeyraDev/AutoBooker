"""Outline generation and CRUD for chapter tree."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.document_parser import DocumentParserAgent
from app.agents.outline_agent import OutlineAgent
from app.database import get_db
from app.models.book import BookStatus
from app.models.chapter import Chapter, ChapterStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.outline import (
    OutlineBookResponse,
    OutlineChapterOut,
    OutlineGenerateIn,
    OutlinePut,
    OutlineSectionOut,
)
from app.llm.providers import resolve_book_outline_model
from app.services import book_service
from app.services.heading_formatter import normalize_outline_sections
from app.services.material_parse_service import get_book_level_writing_rules, get_primary_outline_for_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["outline"])

_DEBUG_LOG = Path(__file__).resolve().parents[4] / "debug-7c6f39.log"


def _agent_ndjson(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "7c6f39",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data,
            "hypothesisId": hypothesis_id,
        }
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


def _chapter_to_outline(ch: Chapter) -> OutlineChapterOut:
    meta = ch.content if isinstance(ch.content, dict) else {}
    sections_raw = normalize_outline_sections(
        [s for s in (meta.get("sections") or []) if isinstance(s, dict)]
    )
    sections = [
        OutlineSectionOut(title=s.get("title", ""), summary=s.get("summary", ""))
        for s in sections_raw
    ]
    return OutlineChapterOut(
        id=ch.id,
        index=ch.index,
        title=ch.title,
        summary=ch.summary,
        key_points=list(meta.get("key_points") or []),
        estimated_words=int(meta.get("estimated_words") or 3000),
        sections=sections,
        word_count=ch.word_count or 0,
        status=ch.status,
    )


@router.get("/{book_id}/outline", response_model=OutlineBookResponse)
def get_outline(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    chapters = (
        db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.index.asc()).all()
    )
    outs = [_chapter_to_outline(c) for c in chapters]
    total_est = sum(o.estimated_words for o in outs) or (book.target_words or 0)
    return OutlineBookResponse(
        title=book.title,
        total_chapters=len(outs),
        estimated_words=total_est,
        chapters=outs,
    )


def _restore_outline_book_status(db: Session, book, previous_status: BookStatus) -> None:
    """大纲生成失败时恢复书稿状态，避免永久卡在 outline_generating。"""
    has_chapters = (
        db.query(Chapter.id).filter(Chapter.book_id == book.id).limit(1).first() is not None
    )
    if has_chapters:
        book.status = BookStatus.outline_ready
    elif previous_status in (BookStatus.setup, BookStatus.outline_ready):
        book.status = previous_status
    else:
        book.status = BookStatus.setup
    db.commit()


@router.post("/{book_id}/outline", response_model=OutlineBookResponse)
def generate_outline(
    book_id: UUID,
    body: OutlineGenerateIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    _agent_ndjson(
        "outline.py:generate_outline",
        "after get_book",
        {"book_id": str(book_id), "status": str(book.status)},
        "H4",
    )
    if book.status == BookStatus.outline_generating:
        has_chapters = (
            db.query(Chapter.id).filter(Chapter.book_id == book.id).limit(1).first() is not None
        )
        previous_status = BookStatus.outline_ready if has_chapters else BookStatus.setup
    elif book.status in (BookStatus.setup, BookStatus.outline_ready):
        previous_status = book.status
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Book must be in setup or outline_ready to generate outline",
        )
    book.status = BookStatus.outline_generating
    db.commit()

    body = body or OutlineGenerateIn()

    try:
        query = (body.topic_override or book.title) + " " + (book.discipline or "")
        parser = DocumentParserAgent(db, book.id)
        snippets = parser.retrieve(query.strip() or book.title, top_k=5)
        _agent_ndjson(
            "outline.py:generate_outline",
            "after retrieve",
            {"snippet_count": len(snippets)},
            "H2",
        )

        cfg = {
            "book_type": book.book_type.value,
            "style_type": book.style_type,
            "topic": body.topic_override or book.title,
            "target_audience": body.target_audience or book.target_audience or "大众读者",
            "target_words": book.target_words or 80000,
            "citation_style": book.citation_style.value if book.citation_style else "无需引用",
            "discipline": book.discipline,
            "topic_tags": list(book.topic_tags or []),
            "topic_brief": (body.topic_brief or book.topic_brief or "").strip() or None,
            "primary_outline": get_primary_outline_for_book(db, book.id),
            "writing_rules": get_book_level_writing_rules(db, book.id),
        }

        agent = OutlineAgent()
        chat_model = resolve_book_outline_model(book, user)
        outline = agent.generate(cfg, snippets, model=chat_model)

        db.query(Chapter).filter(Chapter.book_id == book.id).delete()

        for ch in outline.get("chapters", []):
            raw_sections = ch.get("sections", [])
            sections = (
                normalize_outline_sections(raw_sections)
                if isinstance(raw_sections, list)
                else []
            )
            meta = {
                "key_points": ch.get("key_points", []),
                "sections": sections,
                "estimated_words": ch.get("estimated_words", 3000),
            }
            db.add(
                Chapter(
                    book_id=book.id,
                    index=ch["index"],
                    title=ch["title"],
                    summary=ch.get("summary"),
                    content=meta,
                    word_count=0,
                    status=ChapterStatus.pending,
                )
            )

        if book.allow_title_optimization:
            new_title = (outline.get("title") or "").strip()
            if new_title:
                book.title = new_title[:500]
        book.constitution_stale = True
        from app.services.preface_service import get_preface, set_preface

        preface_brief = (outline.get("preface_brief") or "").strip()
        pf = get_preface(book)
        if preface_brief:
            pf["brief"] = preface_brief
            pf["status"] = "ready"
            set_preface(book, pf)
        book.status = BookStatus.outline_ready
        db.commit()
        db.refresh(book)

        chapters = (
            db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.index.asc()).all()
        )
        outs = [_chapter_to_outline(c) for c in chapters]
        total_est = int(outline.get("estimated_words") or sum(o.estimated_words for o in outs))
        _agent_ndjson(
            "outline.py:generate_outline",
            "success",
            {"total_chapters": len(outs), "estimated_words": total_est},
            "H3",
        )
        return OutlineBookResponse(
            title=book.title,
            total_chapters=len(outs),
            estimated_words=total_est,
            chapters=outs,
        )
    except HTTPException:
        _restore_outline_book_status(db, book, previous_status)
        raise
    except Exception as e:
        _agent_ndjson(
            "outline.py:generate_outline",
            "exception",
            {"exc_type": type(e).__name__, "exc_msg": str(e)[:800]},
            "H1-H5",
        )
        logger.exception("outline generation failed")
        _restore_outline_book_status(db, book, previous_status)
        detail = f"{type(e).__name__}: {str(e)}"
        if len(detail) > 2000:
            detail = detail[:2000] + "…"
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=detail) from e


@router.put("/{book_id}/outline", response_model=OutlineBookResponse)
def update_outline(
    book_id: UUID,
    body: OutlinePut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)

    for p in body.chapters:
        ch = db.query(Chapter).filter(Chapter.book_id == book.id, Chapter.index == p.index).first()
        if not ch:
            continue
        if p.title is not None:
            ch.title = p.title
        if p.summary is not None:
            ch.summary = p.summary
        meta = dict(ch.content) if isinstance(ch.content, dict) else {}
        if p.key_points is not None:
            meta["key_points"] = p.key_points
        if p.estimated_words is not None:
            meta["estimated_words"] = p.estimated_words
        if p.sections is not None:
            dumped = [s.model_dump() for s in p.sections]
            meta["sections"] = normalize_outline_sections(dumped)
        ch.content = meta

    if body.confirm_start_writing:
        book.status = BookStatus.writing
    else:
        book.constitution_stale = True

    db.commit()
    db.refresh(book)

    chapters = (
        db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.index.asc()).all()
    )
    outs = [_chapter_to_outline(c) for c in chapters]
    total_est = sum(o.estimated_words for o in outs) or (book.target_words or 0)
    return OutlineBookResponse(
        title=book.title,
        total_chapters=len(outs),
        estimated_words=total_est,
        chapters=outs,
    )
