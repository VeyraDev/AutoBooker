"""Assemble structured context for startup assistant turns."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.material import WritingRequirement
from app.models.source_segment import SourceSegment
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.services.sources.source_library_service import SourceLibraryService

_CHAPTER_RE = re.compile(
    r"(?:第\s*[一二三四五六七八九十百千零〇两\d]+\s*章|[Cc]hapter\s+\d+|\d+[\.、．]\s*\S+)"
)


BOOK_SETTING_KEYS = (
    "title",
    "book_type",
    "style_type",
    "target_audience",
    "disciplines",
    "topic_brief",
    "target_words",
    "topic_tags",
    "citation_style",
)


def current_book_settings(book: Book) -> dict[str, Any]:
    return {
        "title": book.title or "",
        "book_type": book.book_type.value if book.book_type else None,
        "style_type": book.style_type,
        "target_audience": book.target_audience or "",
        "disciplines": list(book.disciplines or []),
        "topic_brief": book.topic_brief or "",
        "target_words": book.target_words,
        "topic_tags": list(book.topic_tags or []),
        "citation_style": book.citation_style.value if book.citation_style else None,
    }


def get_setting_origins(book: Book) -> dict[str, Any]:
    settings = book.ai_inferred_settings if isinstance(book.ai_inferred_settings, dict) else {}
    raw = settings.get("setting_origins")
    return dict(raw) if isinstance(raw, dict) else {}


def set_setting_origin(book: Book, field: str, origin: str) -> None:
    settings = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    origins = dict(settings.get("setting_origins") or {})
    from datetime import datetime, timezone

    origins[field] = {
        "origin": origin,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    settings["setting_origins"] = origins
    book.ai_inferred_settings = settings


def protected_origins() -> frozenset[str]:
    return frozenset({"user_manual", "user_explicit"})


def confirmed_requirements(db: Session, book_id: UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(WritingRequirement)
        .filter(WritingRequirement.book_id == book_id, WritingRequirement.active.is_(True))
        .order_by(WritingRequirement.created_at.desc())
        .limit(40)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "category": r.category,
            "content": (r.content or "")[:500],
            "strength": r.strength,
        }
        for r in rows
    ]


def uploaded_sources(db: Session, book: Book) -> list[dict[str, Any]]:
    lib = SourceLibraryService(db)
    items = lib.list_sources(book)
    out: list[dict[str, Any]] = []
    for item in items[:30]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "source_id": str(item.get("id") or ""),
                "filename": str(item.get("title") or ""),
                "parse_status": str(item.get("status") or "parsed"),
                "content_summary": str(item.get("summary") or "")[:1500],
                "structured_profile": item.get("structured_profile")
                if isinstance(item.get("structured_profile"), dict)
                else {},
                "usage_limits": [],
                "detected_roles": list(item.get("detected_roles") or []),
            }
        )
    return out


def _segment_outline_stats(text: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    chapter_lines = [ln for ln in lines if _CHAPTER_RE.search(ln)]
    has_titles = len(chapter_lines) >= 2
    # Heuristic: summaries if many non-chapter lines after chapters
    prose = [ln for ln in lines if ln not in chapter_lines and len(ln) > 20]
    has_summaries = len(prose) >= max(2, len(chapter_lines) // 2)
    section_hits = sum(1 for ln in lines if re.search(r"第.+节|^\d+\.\d+", ln))
    chapter_count = len(chapter_lines)
    score = 0.0
    if has_titles:
        score += 0.45
    if has_summaries:
        score += 0.35
    if section_hits >= chapter_count and chapter_count:
        score += 0.2
    return {
        "chapter_count": chapter_count,
        "section_count": section_hits,
        "has_chapter_titles": has_titles,
        "has_chapter_summaries": has_summaries,
        "has_sections": section_hits > 0,
        "completeness_score": round(min(score, 1.0), 2),
    }


def outline_candidates(db: Session, book_id: UUID) -> list[dict[str, Any]]:
    segs = (
        db.query(SourceSegment)
        .filter(SourceSegment.book_id == book_id)
        .order_by(SourceSegment.created_at.desc())
        .limit(40)
        .all()
    )
    out: list[dict[str, Any]] = []
    for seg in segs:
        st = seg.segment_type.value if seg.segment_type else ""
        text = "\n".join(x for x in [seg.summary or "", seg.excerpt or ""] if x)
        if st not in {"outline", "manuscript", "project_brief"} and not _CHAPTER_RE.search(text):
            continue
        stats = _segment_outline_stats(text)
        if stats["chapter_count"] < 2 and st != "outline":
            continue
        out.append(
            {
                "source_id": str(seg.id),
                "segment_type": st,
                **stats,
            }
        )
        if len(out) >= 8:
            break
    return out


def build_startup_context(
    db: Session,
    book: Book,
    *,
    assistant_mode: str,
    user_message: str,
    recent_conversation: list[dict[str, str]],
) -> dict[str, Any]:
    memory_svc = ProjectMemoryService(db)
    memories = memory_svc.list_memories(book.id)
    confirmed = [
        {"memory_type": getattr(m.memory_type, "value", m.memory_type), "content": m.content}
        for m in memories
        if getattr(m, "confirmed", False)
    ][:30]
    return {
        "assistant_mode": assistant_mode,
        "current_book_settings": current_book_settings(book),
        "setting_origins": get_setting_origins(book),
        "confirmed_requirements": confirmed_requirements(db, book.id),
        "uploaded_sources": uploaded_sources(db, book),
        "outline_candidates": outline_candidates(db, book.id),
        "confirmed_project_memory": confirmed,
        "recent_conversation": recent_conversation,
        "user_message": user_message,
        "outline_route_current": (
            (book.ai_inferred_settings or {}).get("outline_route")
            if isinstance(book.ai_inferred_settings, dict)
            else None
        ),
    }
