"""Quick-fill operation snapshots for undo."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.book import Book, BookType, CitationStyle
from app.services.assistant.book_settings_context import BOOK_SETTING_KEYS, current_book_settings


def snapshot_settings(book: Book) -> dict[str, Any]:
    return current_book_settings(book)


def record_quick_fill(
    book: Book,
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    turn_id: str | None = None,
) -> str:
    settings = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    ops = list(settings.get("quick_fill_ops") or [])
    op_id = str(uuid4())
    ops.append(
        {
            "operation_id": op_id,
            "operation_type": "assistant_quick_fill",
            "before": before,
            "after": after,
            "turn_id": turn_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    settings["quick_fill_ops"] = ops[-20:]
    book.ai_inferred_settings = settings
    return op_id


def undo_quick_fill(book: Book, operation_id: str | None = None) -> dict[str, Any]:
    settings = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    ops = list(settings.get("quick_fill_ops") or [])
    if not ops:
        raise ValueError("没有可撤销的快速补齐记录")

    target = None
    if operation_id:
        for op in reversed(ops):
            if op.get("operation_id") == operation_id:
                target = op
                break
        if not target:
            raise ValueError("operation_id not found")
    else:
        target = ops[-1]

    before = target.get("before") if isinstance(target.get("before"), dict) else {}
    _restore_settings(book, before)

    # drop this and any ops after it
    idx = ops.index(target)
    settings["quick_fill_ops"] = ops[:idx]
    book.ai_inferred_settings = settings
    return {"operation_id": target.get("operation_id"), "restored": before}


def _restore_settings(book: Book, data: dict[str, Any]) -> None:
    if "title" in data and data["title"] is not None:
        book.title = str(data["title"])[:500]
    if data.get("book_type") in ("nonfiction", "academic"):
        book.book_type = BookType(data["book_type"])
    if "style_type" in data:
        book.style_type = data.get("style_type")
    if "target_audience" in data:
        book.target_audience = (str(data.get("target_audience") or "")[:500] or None)
    if "disciplines" in data:
        discs = data.get("disciplines") if isinstance(data.get("disciplines"), list) else []
        book.disciplines = [str(d)[:100] for d in discs if str(d).strip()][:12]
        book.discipline = book.disciplines[0] if book.disciplines else None
    if "topic_brief" in data:
        book.topic_brief = (str(data.get("topic_brief") or "")[:20_000] or None)
    if "target_words" in data:
        try:
            tw = int(data["target_words"]) if data["target_words"] is not None else None
            book.target_words = tw
        except (TypeError, ValueError):
            pass
    if "topic_tags" in data:
        tags = data.get("topic_tags") if isinstance(data.get("topic_tags"), list) else []
        book.topic_tags = [str(t)[:80] for t in tags if str(t).strip()][:40]
    if "citation_style" in data:
        cs = data.get("citation_style")
        if cs in (None, "none", ""):
            book.citation_style = None
        elif cs in {c.value for c in CitationStyle}:
            book.citation_style = CitationStyle(cs)
