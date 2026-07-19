"""Book format strategy — generate, patch, confirm."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.models.book import Book
from app.models.book_format_strategy import BookFormatStrategy, FormatStrategyStatus
from app.models.chapter import Chapter
from app.models.intake import ProjectIntake
from app.prompts.format_strategy.generate import FORMAT_STRATEGY_INSTRUCTION
from app.services.citation_service import is_bibliography_chapter
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_COLUMN_KEYS = (
    "column_name",
    "purpose",
    "appearance_condition",
    "required",
    "default_position",
    "forbidden_usage",
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_column(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    name = str(row.get("column_name") or "").strip()
    if not name:
        return None
    return {
        "column_name": name[:120],
        "purpose": str(row.get("purpose") or "").strip()[:500],
        "appearance_condition": str(row.get("appearance_condition") or "").strip()[:500],
        "required": bool(row.get("required")),
        "default_position": str(row.get("default_position") or "").strip()[:200],
        "forbidden_usage": str(row.get("forbidden_usage") or "").strip()[:300],
    }


def _normalize_columns(rows: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in _as_list(rows):
        col = _normalize_column(row)
        if col:
            out.append(col)
    return out[:20]


def _normalize_chapter_suggestions(raw: Any) -> dict[str, list[dict[str, Any]]]:
    data = _as_dict(raw)
    out: dict[str, list[dict[str, Any]]] = {}
    for key, rows in data.items():
        idx = str(key).strip()
        if not idx.isdigit():
            continue
        cols = _normalize_columns(rows)
        if cols:
            out[idx] = cols[:8]
    return out


def _unique_strings(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


class FormatStrategyService:
    def __init__(self, db: Session):
        self.db = db

    def get_confirmed(self, book_id: UUID) -> BookFormatStrategy | None:
        return (
            self.db.query(BookFormatStrategy)
            .filter(
                BookFormatStrategy.book_id == book_id,
                BookFormatStrategy.status == FormatStrategyStatus.confirmed,
            )
            .order_by(BookFormatStrategy.version.desc())
            .first()
        )

    def get_draft(self, book_id: UUID) -> BookFormatStrategy | None:
        return (
            self.db.query(BookFormatStrategy)
            .filter(
                BookFormatStrategy.book_id == book_id,
                BookFormatStrategy.status == FormatStrategyStatus.draft,
            )
            .order_by(BookFormatStrategy.version.desc())
            .first()
        )

    def get_active(self, book_id: UUID) -> BookFormatStrategy | None:
        confirmed = self.get_confirmed(book_id)
        if confirmed:
            return confirmed
        return self.get_draft(book_id)

    def _next_version(self, book_id: UUID) -> int:
        count = self.db.query(BookFormatStrategy).filter(BookFormatStrategy.book_id == book_id).count()
        return count + 1

    def _supersede_confirmed(self, book_id: UUID) -> None:
        rows = (
            self.db.query(BookFormatStrategy)
            .filter(
                BookFormatStrategy.book_id == book_id,
                BookFormatStrategy.status == FormatStrategyStatus.confirmed,
            )
            .all()
        )
        for row in rows:
            row.status = FormatStrategyStatus.superseded

    def get_draft_or_create(self, book: Book) -> BookFormatStrategy:
        draft = self.get_draft(book.id)
        if draft:
            return draft
        strategy = BookFormatStrategy(
            book_id=book.id,
            version=self._next_version(book.id),
            status=FormatStrategyStatus.draft,
            book_level_columns=[],
            conditional_columns=[],
            forbidden_patterns=[],
            chapter_suggestions={},
        )
        self.db.add(strategy)
        self.db.flush()
        return strategy

    def _outline_summary(self, book_id: UUID) -> str:
        chapters = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book_id)
            .order_by(Chapter.index.asc())
            .all()
        )
        lines: list[str] = []
        for ch in chapters:
            if is_bibliography_chapter(ch):
                continue
            meta = ch.content if isinstance(ch.content, dict) else {}
            labels = meta.get("column_labels") or []
            label_bit = f" 现有栏目标签：{' · '.join(str(x) for x in labels)}" if labels else ""
            lines.append(
                f"第{ch.index}章 {ch.title}：{(ch.summary or '')[:200]}{label_bit}"
            )
        return "\n".join(lines) if lines else "（尚无大纲章节）"

    def generate(self, book: Book, *, force: bool = False) -> BookFormatStrategy:
        existing = self.get_draft(book.id)
        if existing and not force and (existing.book_level_columns or existing.chapter_suggestions):
            return existing

        wcb = __import__(
            "app.services.writing.writing_context_builder",
            fromlist=["WritingContextBuilder"],
        ).WritingContextBuilder(self.db)
        snap = wcb.build_snapshot(book.id)
        context_block = wcb.to_prompt_block(snap)
        outline_block = self._outline_summary(book.id)

        prompt = f"""{FORMAT_STRATEGY_INSTRUCTION}

【写作依据】
{context_block[:8000]}

【书稿信息】
书名：{book.title}
类型：{book.book_type.value if book.book_type else 'general'}
读者：{book.target_audience or '大众读者'}
学科：{book.discipline or '—'}

【大纲摘要】
{outline_block[:6000]}
"""
        try:
            out = LLMClient().chat_completion(
                [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
                max_tokens=3500,
                temperature=0.35,
            )
            data = parse_llm_json(out)
        except Exception:
            logger.exception("format strategy LLM generate failed book=%s", book.id)
            data = {}

        strategy = existing or self.get_draft_or_create(book)
        strategy.book_level_columns = _normalize_columns(data.get("book_level_columns"))
        strategy.conditional_columns = _normalize_columns(data.get("conditional_columns"))
        strategy.forbidden_patterns = _unique_strings(_as_list(data.get("forbidden_patterns")))[:15]
        strategy.chapter_suggestions = _normalize_chapter_suggestions(data.get("chapter_suggestions"))
        self.db.flush()
        return strategy

    def patch(self, strategy: BookFormatStrategy, patch: dict[str, Any]) -> BookFormatStrategy:
        if strategy.status != FormatStrategyStatus.draft:
            raise ValueError("Only draft format strategy can be patched")
        if "book_level_columns" in patch and patch["book_level_columns"] is not None:
            strategy.book_level_columns = _normalize_columns(patch["book_level_columns"])
        if "conditional_columns" in patch and patch["conditional_columns"] is not None:
            strategy.conditional_columns = _normalize_columns(patch["conditional_columns"])
        if "forbidden_patterns" in patch and patch["forbidden_patterns"] is not None:
            strategy.forbidden_patterns = _unique_strings(_as_list(patch["forbidden_patterns"]))[:15]
        if "chapter_suggestions" in patch and patch["chapter_suggestions"] is not None:
            strategy.chapter_suggestions = _normalize_chapter_suggestions(patch["chapter_suggestions"])
        self.db.flush()
        return strategy

    def _sync_column_labels(self, book_id: UUID, chapter_suggestions: dict[str, list[dict[str, Any]]]) -> None:
        chapters = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book_id)
            .order_by(Chapter.index.asc())
            .all()
        )
        for ch in chapters:
            if is_bibliography_chapter(ch):
                continue
            key = str(ch.index)
            suggestions = chapter_suggestions.get(key) or []
            labels = [s["column_name"] for s in suggestions if s.get("column_name")]
            meta = dict(ch.content) if isinstance(ch.content, dict) else {}
            if labels:
                meta["column_labels"] = labels[:8]
            elif key in chapter_suggestions:
                meta.pop("column_labels", None)
            ch.content = meta
        self.db.flush()

    def confirm(self, book: Book, strategy: BookFormatStrategy) -> BookFormatStrategy:
        if strategy.status != FormatStrategyStatus.draft:
            raise ValueError("Only draft format strategy can be confirmed")
        self._supersede_confirmed(book.id)
        strategy.status = FormatStrategyStatus.confirmed
        suggestions = _normalize_chapter_suggestions(strategy.chapter_suggestions)
        strategy.chapter_suggestions = suggestions
        self._sync_column_labels(book.id, suggestions)

        intake = (
            self.db.query(ProjectIntake)
            .filter(ProjectIntake.book_id == book.id)
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if intake:
            intake.confirmed_format_strategy_id = strategy.id
        self.db.flush()
        return strategy

    def to_dict(self, strategy: BookFormatStrategy | None) -> dict[str, Any] | None:
        if not strategy:
            return None
        return {
            "id": str(strategy.id),
            "book_id": str(strategy.book_id),
            "version": strategy.version,
            "status": strategy.status.value,
            "book_level_columns": list(strategy.book_level_columns or []),
            "conditional_columns": list(strategy.conditional_columns or []),
            "forbidden_patterns": list(strategy.forbidden_patterns or []),
            "chapter_suggestions": dict(strategy.chapter_suggestions or {}),
        }

    def chapter_slice(self, strategy: BookFormatStrategy | None, chapter_index: int) -> list[dict[str, Any]]:
        if not strategy:
            return []
        suggestions = _normalize_chapter_suggestions(strategy.chapter_suggestions)
        key = str(chapter_index)
        chapter_cols = list(suggestions.get(key) or [])
        if strategy.status == FormatStrategyStatus.confirmed:
            book_level = _normalize_columns(strategy.book_level_columns)
            conditional = _normalize_columns(strategy.conditional_columns)
            seen = {c["column_name"] for c in chapter_cols}
            for col in book_level + conditional:
                if col["column_name"] not in seen:
                    chapter_cols.append(col)
                    seen.add(col["column_name"])
        return chapter_cols[:12]

    def format_summary_block(self, strategy: BookFormatStrategy | None) -> str:
        if not strategy:
            return ""
        lines: list[str] = []
        for label, key in (
            ("书级固定栏目", "book_level_columns"),
            ("条件栏目", "conditional_columns"),
        ):
            cols = _normalize_columns(getattr(strategy, key, []))
            if not cols:
                continue
            lines.append(f"【{label}】")
            for col in cols[:8]:
                cond = col.get("appearance_condition") or "—"
                lines.append(f"- {col['column_name']}：{col.get('purpose') or '—'}（出现条件：{cond}）")
        forbidden = list(strategy.forbidden_patterns or [])
        if forbidden:
            lines.append("【禁止模板化】")
            lines.extend(f"- {x}" for x in forbidden[:8])
        return "\n".join(lines).strip()

    def chapter_format_block(self, strategy: BookFormatStrategy | None, chapter_index: int) -> str:
        cols = self.chapter_slice(strategy, chapter_index)
        if not cols:
            return ""
        lines = [f"第 {chapter_index} 章栏目策略："]
        for col in cols:
            parts = [f"- {col['column_name']}"]
            if col.get("purpose"):
                parts.append(f"用途：{col['purpose']}")
            if col.get("appearance_condition"):
                parts.append(f"出现条件：{col['appearance_condition']}")
            if col.get("default_position"):
                parts.append(f"建议位置：{col['default_position']}")
            if col.get("forbidden_usage"):
                parts.append(f"禁止：{col['forbidden_usage']}")
            if col.get("required"):
                parts.append("（本章建议包含）")
            lines.append("；".join(parts))
        return "\n".join(lines)

    def suggestions_to_json(self, strategy: BookFormatStrategy) -> str:
        return json.dumps(self.to_dict(strategy) or {}, ensure_ascii=False)
