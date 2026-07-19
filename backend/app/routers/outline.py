"""Outline generation and CRUD for chapter tree."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.document_parser import DocumentParserAgent
from app.agents.outline_agent import OutlineAgent
from app.database import get_db
from app.models.book import BookStatus
from app.models.book_job import BookJob, BookJobStatus
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
from app.services.material_parse_service import (
    get_book_level_writing_rules,
    get_primary_outline_for_book,
    merge_outline_with_primary,
)
from app.services.citation_service import is_bibliography_chapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["outline"])

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
        column_labels=[str(x) for x in (meta.get("column_labels") or []) if str(x).strip()],
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
    outs = [_chapter_to_outline(c) for c in chapters if not is_bibliography_chapter(c)]
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


def _mark_auto_job_writing_started(db: Session, book_id: UUID) -> None:
    auto_job = (
        db.query(BookJob)
        .filter(
            BookJob.book_id == book_id,
            BookJob.status == BookJobStatus.completed,
        )
        .order_by(BookJob.created_at.desc())
        .first()
    )
    if not auto_job:
        return
    checkpoint = dict(auto_job.checkpoint_json or {})
    if not checkpoint.get("ready_for_editor"):
        return
    checkpoint["writing_started"] = True
    auto_job.checkpoint_json = checkpoint


@router.post("/{book_id}/outline", response_model=OutlineBookResponse)
def generate_outline(
    book_id: UUID,
    body: OutlineGenerateIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
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
        from app.services.writing.writing_context_builder import WritingContextBuilder

        wcb = WritingContextBuilder(db)
        snap = wcb.build_for_outline(book.id)
        cfg["writing_context"] = wcb.to_prompt_block(snap)

        agent = OutlineAgent()
        chat_model = resolve_book_outline_model(book, user)
        outline = agent.generate(cfg, snippets, model=chat_model)
        outline = merge_outline_with_primary(
            outline,
            get_primary_outline_for_book(db, book.id),
        )

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
            labels = ch.get("column_labels")
            if isinstance(labels, list) and labels:
                meta["column_labels"] = [str(x).strip() for x in labels if str(x).strip()][:8]
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

        db.flush()
        from app.services.citation_nodes import refresh_book_citation_rendering
        from app.services.citation_service import sync_book_bibliography

        refresh_book_citation_rendering(db, book)
        sync_book_bibliography(db, book, commit=False)
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

        try:
            from app.services.writing.format_strategy_service import FormatStrategyService

            FormatStrategyService(db).generate(book, force=True)
            db.commit()
        except Exception:
            logger.exception("format strategy auto-generate failed after outline book=%s", book.id)

        chapters = (
            db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.index.asc()).all()
        )
        outs = [_chapter_to_outline(c) for c in chapters if not is_bibliography_chapter(c)]
        total_est = int(outline.get("estimated_words") or sum(o.estimated_words for o in outs))
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
        logger.exception("outline generation failed")
        _restore_outline_book_status(db, book, previous_status)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="大纲生成未能完成，请稍后重试。书稿设定已保留。",
        ) from e


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
        _mark_auto_job_writing_started(db, book.id)
    else:
        book.constitution_stale = True

    db.commit()
    db.refresh(book)

    chapters = (
        db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.index.asc()).all()
    )
    outs = [_chapter_to_outline(c) for c in chapters if not is_bibliography_chapter(c)]
    total_est = sum(o.estimated_words for o in outs) or (book.target_words or 0)
    return OutlineBookResponse(
        title=book.title,
        total_chapters=len(outs),
        estimated_words=total_est,
        chapters=outs,
    )
