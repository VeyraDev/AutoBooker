"""检索词提炼（Query Refiner）。"""

from __future__ import annotations

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

_MIN_ENGLISH_QUERIES = 3


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _is_english_query(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if _has_cjk(t):
        return False
    return bool(re.search(r"[A-Za-z]", t))


def _order_queries(queries: list[str]) -> list[str]:
    """中文在前，英文在后；两类都保留。"""
    cn = [q for q in queries if _has_cjk(q)]
    en = [q for q in queries if _is_english_query(q)]
    other = [q for q in queries if q not in cn and q not in en]
    return list(dict.fromkeys(cn + en + other))


def _fallback_english_queries(raw: str) -> list[str]:
    q = (raw or "").strip()
    out: list[str] = []
    if "大模型" in q or "模型" in q:
        out.extend(["large language model", "LLM fine-tuning", "transformer architecture"])
    elif "AI" in q.upper() or "人工智能" in q:
        out.extend(["artificial intelligence", "machine learning", "deep learning"])
    elif q and _is_english_query(q):
        out.append(q)
    else:
        out.extend(["machine learning", "software engineering"])
    return out


def _ensure_english_queries(queries: list[str], raw: str) -> list[str]:
    en = [q for q in queries if _is_english_query(q)]
    if len(en) >= _MIN_ENGLISH_QUERIES:
        return queries
    for fb in _fallback_english_queries(raw):
        if fb not in queries:
            queries.append(fb)
        if len([q for q in queries if _is_english_query(q)]) >= _MIN_ENGLISH_QUERIES:
            break
    return queries


def _fallback_refine(raw: str) -> dict[str, Any]:
    q = (raw or "").strip()
    if not q:
        return {"refined_queries": [], "must_include": [], "must_exclude": []}
    cleaned = re.sub(r"^(怎样|如何|怎么)", "", q).strip()
    cn = cleaned or q
    queries = _order_queries([cn, *_fallback_english_queries(q)])
    if cleaned != q and cleaned:
        queries = _order_queries(list(dict.fromkeys([*queries, q])))
    queries = _ensure_english_queries(queries, q)[:8]
    return {
        "refined_queries": queries,
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
    queries = [str(x).strip() for x in queries if str(x).strip()]
    queries = _order_queries(queries)
    queries = _ensure_english_queries(queries, raw_query or book.title or "")
    queries = queries[:8]
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
