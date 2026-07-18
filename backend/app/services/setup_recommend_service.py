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
from app.models.user import User
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
        if len(out) >= 3:
            break
    return out


def _normalize_discipline_candidates(items: Any, disciplines: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(items, list):
        for item in items:
            raw = item if isinstance(item, dict) else {"name": item}
            name = str(raw.get("name") or "").strip()[:100]
            if not name or any(c["name"] == name for c in out):
                continue
            reason = str(raw.get("reason") or "").strip()[:240]
            ambiguity_note = str(raw.get("ambiguity_note") or "").strip()[:240]
            out.append(
                {
                    "name": name,
                    "reason": reason or "该领域会影响本书术语解释、证据选择和论证边界。",
                    "ambiguity_note": ambiguity_note,
                }
            )
            if len(out) >= 3:
                break
    for name in disciplines:
        if not any(c["name"] == name for c in out):
            out.append(
                {
                    "name": name,
                    "reason": "该领域会影响本书术语解释、证据选择和论证边界。",
                    "ambiguity_note": "",
                }
            )
            if len(out) >= 3:
                break
    return out


def _discipline_confirmation_note(value: Any) -> str:
    note = str(value or "").strip()
    if note:
        return note[:300]
    return "学科领域用于约束同名术语解释、证据标准和论证方式，避免自造理论、名词或抽象类比。"


def recommend_book_setup(
    book: Book,
    user: User,
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
            "discipline_candidates": _normalize_discipline_candidates(
                payload.get("discipline_candidates"),
                _normalize_disciplines(payload.get("disciplines")),
            ),
            "discipline_confirmation_note": _discipline_confirmation_note(
                payload.get("discipline_confirmation_note")
            ),
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
    model = resolve_book_outline_model(book, user, db)
    client = LLMClient()
    last_err: str | None = None
    data: dict[str, Any] | None = None
    for attempt in range(3):
        extra = ""
        if last_err:
            extra = (
                f"\n\n上次输出不是合法 JSON（{last_err}）。"
                "请严格只输出 JSON：字符串内换行写 \\n，内部双引号写 \\\"，不要 markdown 代码块。"
            )
        try:
            out = client.chat_completion(
                [
                    {"role": "system", "content": SETUP_RECOMMEND_SYSTEM},
                    {"role": "user", "content": user_msg + extra},
                ],
                model=model,
                max_tokens=1200,
                temperature=0.35,
            )
            data = parse_llm_json(out)
            break
        except Exception as exc:
            last_err = str(exc)
            logger.warning(
                "setup recommend parse failed book=%s attempt=%s: %s",
                book.id,
                attempt + 1,
                exc,
            )
    if data is None:
        logger.warning("setup recommend failed book=%s: %s", book.id, last_err)
        raise RuntimeError(last_err or "setup recommend JSON parse failed")

    disciplines = _normalize_disciplines(data.get("disciplines"))
    discipline_candidates = _normalize_discipline_candidates(data.get("discipline_candidates"), disciplines)
    if not disciplines and discipline_candidates:
        disciplines = [c["name"] for c in discipline_candidates[:3]]
    result = {
        "from_cache": False,
        "cache_key": cache_key,
        "recommended_tags": _normalize_tags(data.get("recommended_tags")),
        "target_audience": str(data.get("target_audience") or "").strip()[:2000],
        "disciplines": disciplines,
        "discipline_candidates": discipline_candidates,
        "discipline_confirmation_note": _discipline_confirmation_note(
            data.get("discipline_confirmation_note")
        ),
        "topic_brief": str(data.get("topic_brief") or "").strip()[:8000],
    }
    book.setup_recommendation_cache = {
        "cache_key": cache_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "recommended_tags": result["recommended_tags"],
            "target_audience": result["target_audience"],
            "disciplines": result["disciplines"],
            "discipline_candidates": result["discipline_candidates"],
            "discipline_confirmation_note": result["discipline_confirmation_note"],
            "topic_brief": result["topic_brief"],
        },
    }
    db.commit()
    db.refresh(book)
    return result
