"""检索词提炼（Query Refiner）。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.client import LLMClient
from app.models.book import Book
from app.models.chapter import Chapter
from app.prompts.literature_query import QUERY_REFINE_PROMPT
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def _fallback_refine(raw: str) -> dict[str, Any]:
    q = (raw or "").strip()
    if not q:
        return {"refined_queries": [], "must_include": [], "must_exclude": []}
    # 简单去口语
    cleaned = re.sub(r"^(怎样|如何|怎么)", "", q).strip()
    return {
        "refined_queries": [cleaned, q] if cleaned != q else [q],
        "must_include": [],
        "must_exclude": ["教育学", "pedagogy"] if "培养" in q and "模型" in q else [],
    }


def refine_literature_query(
    db: Session,
    book: Book,
    *,
    raw_query: str = "",
    scope: str = "book",
    chapter_index: int | None = None,
) -> dict[str, Any]:
    chapter_title = ""
    chapter_summary = ""
    if scope == "chapter" and chapter_index is not None:
        ch = (
            db.query(Chapter)
            .filter(Chapter.book_id == book.id, Chapter.index == chapter_index)
            .first()
        )
        if ch:
            chapter_title = ch.title or ""
            chapter_summary = ch.summary or ""

    tags = book.topic_tags or []
    if isinstance(tags, list):
        tags_line = ", ".join(str(t) for t in tags)
    else:
        tags_line = str(tags)

    client = LLMClient()
    prompt = QUERY_REFINE_PROMPT.format(
        book_title=book.title or "",
        book_type=book.book_type.value if book.book_type else "",
        style_type=book.style_type or "",
        user_material=(book.user_material or "")[:1500],
        chapter_title=chapter_title,
        chapter_summary=chapter_summary[:1500],
        topic_tags=tags_line,
        raw_query=raw_query or book.title or "",
    )
    try:
        out = client.chat_completion(
            [{"role": "user", "content": prompt}],
            model=settings.intent_model,
            max_tokens=600,
            temperature=0.2,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("query refine failed: %s", e)
        data = _fallback_refine(raw_query or book.title or "")

    queries = data.get("refined_queries") or []
    if not isinstance(queries, list):
        queries = []
    queries = [str(x).strip() for x in queries if str(x).strip()][:8]
    if not queries:
        data_fb = _fallback_refine(raw_query or book.title or "")
        queries = data_fb["refined_queries"]

    must_inc = data.get("must_include") or []
    must_exc = data.get("must_exclude") or []
    if not isinstance(must_inc, list):
        must_inc = []
    if not isinstance(must_exc, list):
        must_exc = []

    return {
        "refined_queries": queries,
        "must_include": [str(x) for x in must_inc][:10],
        "must_exclude": [str(x) for x in must_exc][:10],
    }
