"""Book-level memory: aggregate for chapter writing and extract after generation."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import jsonschema
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.client import LLMClient
from app.models.book import Book
from app.models.memory import BookMemory, MemoryType
from app.prompts.memory_extract import MEMORY_EXTRACT_PROMPT, MEMORY_JSON_SCHEMA
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def build_book_memory(book_id: uuid.UUID, chapter_index: int, db: Session) -> dict[str, Any]:
    book = db.get(Book, book_id)
    if not book:
        raise ValueError("Book not found")

    rows = db.query(BookMemory).filter(BookMemory.book_id == book_id).all()

    chapter_summaries: dict[int, str] = {}
    terms: dict[str, str] = {}
    style_anchor = ""

    for r in rows:
        if r.type == MemoryType.summary and r.key == "chapter_summary":
            chapter_summaries[r.chapter_index] = r.value
        elif r.type == MemoryType.term:
            terms[r.key] = r.value
        elif r.type == MemoryType.style and r.key == "style_anchor":
            style_anchor = r.value

    prev_summary = chapter_summaries.get(chapter_index - 1, "无")
    next_summary = chapter_summaries.get(chapter_index + 1, "无")

    citation = book.citation_style.value if book.citation_style else "无"

    return {
        "book_type": book.book_type.value,
        "style_guide": style_anchor or "流畅自然，逻辑清晰",
        "citation_style": citation,
        "terms": terms,
        "prev_summary": prev_summary,
        "next_summary": next_summary,
    }


def _clear_chapter_memory_slots(book_id: uuid.UUID, chapter_index: int, db: Session) -> None:
    db.query(BookMemory).filter(
        BookMemory.book_id == book_id,
        BookMemory.chapter_index == chapter_index,
        BookMemory.key.in_(["chapter_summary", "key_conclusions"]),
    ).delete(synchronize_session=False)
    db.query(BookMemory).filter(
        BookMemory.book_id == book_id,
        BookMemory.chapter_index == chapter_index,
        BookMemory.type == MemoryType.term,
    ).delete(synchronize_session=False)


def extract_chapter_memory(book_id: uuid.UUID, chapter_index: int, content: str, db: Session) -> None:
    if not content.strip():
        return

    client = LLMClient()
    prompt = MEMORY_EXTRACT_PROMPT + "\n\n章节内容：\n" + content[:8000]
    raw = client.chat_completion(
        [{"role": "user", "content": prompt}],
        model=settings.CHAT_MODEL_FAST,
        max_tokens=1024,
        temperature=0.3,
        provider="dashscope",
    )
    try:
        data = parse_llm_json(raw)
        jsonschema.validate(instance=data, schema=MEMORY_JSON_SCHEMA)
    except Exception as e:
        logger.warning("memory extract parse failed: %s", e)
        return

    _clear_chapter_memory_slots(book_id, chapter_index, db)

    db.add(
        BookMemory(
            book_id=book_id,
            chapter_index=chapter_index,
            type=MemoryType.summary,
            key="chapter_summary",
            value=data["summary"],
        )
    )
    db.add(
        BookMemory(
            book_id=book_id,
            chapter_index=chapter_index,
            type=MemoryType.summary,
            key="key_conclusions",
            value=json.dumps(data["key_conclusions"], ensure_ascii=False),
        )
    )

    for term, definition in (data.get("new_terms") or {}).items():
        db.add(
            BookMemory(
                book_id=book_id,
                chapter_index=chapter_index,
                type=MemoryType.term,
                key=term[:500],
                value=definition,
            )
        )

    style_sample = (data.get("style_sample") or "").strip()
    if chapter_index == 1 and style_sample:
        existing = (
            db.query(BookMemory)
            .filter(
                BookMemory.book_id == book_id,
                BookMemory.chapter_index == 0,
                BookMemory.type == MemoryType.style,
                BookMemory.key == "style_anchor",
            )
            .first()
        )
        if existing:
            existing.value = style_sample[:2000]
        else:
            db.add(
                BookMemory(
                    book_id=book_id,
                    chapter_index=0,
                    type=MemoryType.style,
                    key="style_anchor",
                    value=style_sample[:2000],
                )
            )

    db.commit()
