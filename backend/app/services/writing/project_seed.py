"""Unified project seed for settings inference, literature search, and outline topic.

Book title (often the placeholder 「书稿1」) must not drive theme inference.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.book import Book, BookType

logger = logging.getLogger(__name__)

_NONFICTION_STYLES = frozenset(
    {"popular_science", "practical_guide", "reference_tool", "insight_opinion"}
)
_ACADEMIC_STYLES = frozenset(
    {"textbook", "technical_deep_dive", "ai_review_commentary"}
)
_DEFAULT_WORDS = {BookType.nonfiction: 80_000, BookType.academic: 200_000}

_PLACEHOLDER_TITLES = frozenset({"书稿1", "未命名书稿", "untitled", "new book"})


def _normalize_disciplines(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()[:100]
        if text and text not in out:
            out.append(text)
        if len(out) >= 3:
            break
    return out


def _normalize_discipline_candidates(items: object, disciplines: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(items, list):
        for item in items:
            raw = item if isinstance(item, dict) else {"name": item}
            name = str(raw.get("name") or "").strip()[:100]
            if not name or any(c["name"] == name for c in out):
                continue
            out.append(
                {
                    "name": name,
                    "reason": str(raw.get("reason") or "").strip()[:240]
                    or "该领域会影响本书术语解释、证据选择和论证边界。",
                    "ambiguity_note": str(raw.get("ambiguity_note") or "").strip()[:240],
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


def resolve_project_seed(book: Book, db: Session | None = None) -> str:
    """User intent → topic_brief → (non-placeholder) title. Never prefer 「书稿1」."""
    parts: list[str] = []

    if db is not None:
        from app.models.intake import IntakeStatus, ProjectIntake

        intake = (
            db.query(ProjectIntake)
            .filter(
                ProjectIntake.book_id == book.id,
                ProjectIntake.status != IntakeStatus.superseded,
            )
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if intake and (intake.raw_goal_text or "").strip():
            parts.append(intake.raw_goal_text.strip()[:4000])

    brief = (book.topic_brief or "").strip()
    if brief and brief not in parts:
        parts.append(brief[:3000])

    material = (book.user_material or "").strip()
    if material and material not in parts and material not in brief:
        parts.append(material[:2000])

    title = (book.title or "").strip()
    if title and title.lower() not in {t.lower() for t in _PLACEHOLDER_TITLES}:
        if title not in parts:
            parts.append(title)

    seed = "\n".join(parts).strip()
    return seed or title or "未命名主题"


def is_provisional_classification(book: Book) -> bool:
    """True when book still carries create-time default 大众非虚构/入门科普 shell."""
    settings = book.ai_inferred_settings if isinstance(book.ai_inferred_settings, dict) else {}
    if settings.get("classification_confirmed") or settings.get("classification_source") in {
        "user",
        "assistant",
        "inferred",
    }:
        return False
    bt = book.book_type.value if book.book_type else "nonfiction"
    st = (book.style_type or "popular_science").strip()
    return bt == "nonfiction" and st == "popular_science"


def mark_classification_source(book: Book, source: str) -> None:
    settings = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    settings["classification_source"] = source
    if source in {"user", "assistant", "inferred"}:
        settings["classification_confirmed"] = True
    book.ai_inferred_settings = settings


def _normalize_style_key(raw: str) -> str:
    key = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "科普": "popular_science",
        "入门科普": "popular_science",
        "大众科普": "popular_science",
        "实战": "practical_guide",
        "操作": "practical_guide",
        "实用指南": "practical_guide",
        "手册": "reference_tool",
        "工具": "reference_tool",
        "技术手册": "reference_tool",
        "洞察": "insight_opinion",
        "观点": "insight_opinion",
        "教材": "textbook",
        "教科书": "textbook",
        "教学": "textbook",
        "深度": "technical_deep_dive",
        "技术深度": "technical_deep_dive",
        "专著": "technical_deep_dive",
        "研究报告": "technical_deep_dive",
        "博士后": "technical_deep_dive",
        "课题": "technical_deep_dive",
        "评论": "ai_review_commentary",
        "评估": "ai_review_commentary",
    }
    return aliases.get(key, key)


def _coerce_book_type(raw: str) -> BookType | None:
    key = (raw or "").strip().lower()
    if not key:
        return None
    if key in {
        "academic",
        "学术",
        "学术专著",
        "教材",
        "论文",
        "研究报告",
        "博士",
        "硕士",
        "专著",
        "课题",
    }:
        return BookType.academic
    if key in {"nonfiction", "大众非虚构", "非虚构", "科普", "大众"}:
        return BookType.nonfiction
    return None


def _coerce_style(book_type: BookType, raw: str) -> str:
    key = _normalize_style_key(raw)
    allowed = _ACADEMIC_STYLES if book_type == BookType.academic else _NONFICTION_STYLES
    if key in allowed:
        return key
    return "textbook" if book_type == BookType.academic else "popular_science"


def _pair_type_and_style(
    raw_type: str,
    raw_style: str,
    *,
    fallback_type: BookType,
    fallback_style: str,
) -> tuple[BookType, str]:
    """Prefer style→type pairing so academic styles are not crushed into 大众非虚构."""
    style_key = _normalize_style_key(raw_style)
    if style_key in _ACADEMIC_STYLES:
        return BookType.academic, style_key
    if style_key in _NONFICTION_STYLES:
        return BookType.nonfiction, style_key

    book_type = _coerce_book_type(raw_type) or fallback_type
    if not raw_style.strip():
        # Do not silently keep create-time popular_science when type flips to academic
        style = _coerce_style(book_type, fallback_style if fallback_type == book_type else "")
    else:
        style = _coerce_style(book_type, raw_style)
    return book_type, style


def infer_book_settings(book: Book, model: str, db: Session | None = None) -> dict:
    """Suggestion-only inference. Does not mutate Book."""
    from app.services.assistant.suggest_book_settings import suggest_book_settings

    return suggest_book_settings(db, book, model=model, mode="intake")


def infer_and_apply_book_settings(book: Book, model: str, db: Session | None = None) -> str:
    """Compat wrapper for one-click / intake: suggest then apply (with legacy defaults).

    Returns the project_seed used for inference (also for literature / outline).
    """
    from app.services.assistant.suggest_book_settings import (
        apply_book_settings_suggestion,
        suggest_book_settings,
    )

    seed = resolve_project_seed(book, db)
    suggestion = suggest_book_settings(db, book, model=model, mode="intake")
    # Legacy intake paths still fill defaults when fields unresolved
    apply_book_settings_suggestion(book, suggestion, fill_defaults=True)
    if not book.book_type or not (book.style_type or "").strip():
        bt, st = _pair_type_and_style(
            "",
            "",
            fallback_type=book.book_type or BookType.nonfiction,
            fallback_style=(book.style_type or "popular_science"),
        )
        book.book_type = bt
        book.style_type = st
        mark_classification_source(book, "inferred")

    candidates = suggestion.get("discipline_candidates") or []
    if not candidates:
        candidates = _normalize_discipline_candidates([], list(book.disciplines or []))
    reason = ""
    for d in suggestion.get("decisions") or []:
        if isinstance(d, dict) and d.get("field") in {"book_type", "style_type"} and d.get("reason"):
            reason = str(d.get("reason"))[:500]
            break

    prev = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    prev.update(
        {
            "topic_brief": (book.topic_brief or "")[:3000],
            "book_type": book.book_type.value if book.book_type else None,
            "style_type": book.style_type,
            "target_words": book.target_words,
            "disciplines": list(book.disciplines or []),
            "discipline_candidates": candidates,
            "discipline_confirmation_note": "学科领域用于约束同名术语解释、证据标准和论证方式，避免自造理论、名词或抽象类比。",
            "project_seed_preview": seed[:500],
            "inferred_at": datetime.now(timezone.utc).isoformat(),
            "input_hash": hashlib.sha256(seed.encode()).hexdigest(),
            "classification_source": prev.get("classification_source") or "inferred",
            "classification_confirmed": True,
            "classification_reason": reason,
            "unresolved_fields": suggestion.get("unresolved_fields") or [],
        }
    )
    book.ai_inferred_settings = prev
    return seed
