"""书稿设定页轻量推荐服务（与文献检索词分离）。"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.constants.style_types import STYLE_TYPE_LABELS
from app.llm.client import LLMClient
from app.llm.providers import resolve_book_outline_model
from app.models.book import Book, BookType
from app.prompts.setup_recommend import SETUP_RECOMMEND_SYSTEM, SETUP_RECOMMEND_USER_TEMPLATE
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

BOOK_TYPE_LABELS = {
    BookType.nonfiction.value: "大众非虚构",
    BookType.academic.value: "学术专著",
}


def setup_recommend_cache_key(book: Book) -> str:
    raw = "|".join(
        [
            (book.title or "").strip(),
            book.book_type.value if book.book_type else "",
            (book.style_type or "").strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    out: list[str] = []
    for t in tags:
        s = str(t or "").strip()[:80]
        if s and s not in out:
            out.append(s)
        if len(out) >= 10:
            break
    return out


def _normalize_disciplines(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for d in items:
        s = str(d or "").strip()[:100]
        if s and s not in out:
            out.append(s)
        if len(out) >= 8:
            break
    return out


def recommend_book_setup(
    book: Book,
    db: Session,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """返回推荐结果；命中缓存且未 force 时直接返回缓存。"""
    cache_key = setup_recommend_cache_key(book)
    cached = book.setup_recommendation_cache if isinstance(book.setup_recommendation_cache, dict) else None
    if not force and cached and cached.get("cache_key") == cache_key:
        payload = cached.get("payload") or {}
        return {
            "from_cache": True,
            "cache_key": cache_key,
            "recommended_tags": _normalize_tags(payload.get("recommended_tags")),
            "target_audience": str(payload.get("target_audience") or "").strip(),
            "disciplines": _normalize_disciplines(payload.get("disciplines")),
            "topic_brief": str(payload.get("topic_brief") or "").strip(),
        }

    bt = book.book_type.value if book.book_type else "nonfiction"
    st = (book.style_type or "").strip()
    disciplines_existing = book.disciplines if isinstance(book.disciplines, list) else []
    if not disciplines_existing and book.discipline:
        disciplines_existing = [book.discipline]

    user_msg = SETUP_RECOMMEND_USER_TEMPLATE.format(
        title=book.title,
        book_type_label=BOOK_TYPE_LABELS.get(bt, bt),
        style_type_label=STYLE_TYPE_LABELS.get(st, st or "（未指定）"),
        disciplines="、".join(disciplines_existing) if disciplines_existing else "（无）",
    )
    model = resolve_book_outline_model(book)
    client = LLMClient()
    try:
        out = client.chat_completion(
            [
                {"role": "system", "content": SETUP_RECOMMEND_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            model=model,
            max_tokens=1200,
            temperature=0.35,
        )
        data = parse_llm_json(out)
    except Exception as exc:
        logger.warning("setup recommend failed book=%s: %s", book.id, exc)
        raise

    result = {
        "from_cache": False,
        "cache_key": cache_key,
        "recommended_tags": _normalize_tags(data.get("recommended_tags")),
        "target_audience": str(data.get("target_audience") or "").strip()[:2000],
        "disciplines": _normalize_disciplines(data.get("disciplines")),
        "topic_brief": str(data.get("topic_brief") or "").strip()[:8000],
    }
    book.setup_recommendation_cache = {
        "cache_key": cache_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "recommended_tags": result["recommended_tags"],
            "target_audience": result["target_audience"],
            "disciplines": result["disciplines"],
            "topic_brief": result["topic_brief"],
        },
    }
    db.commit()
    db.refresh(book)
    return result
