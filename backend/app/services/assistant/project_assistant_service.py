"""Project startup assistant — multi-turn conversation."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.providers import resolve_assistant_model
from app.models.assistant_turn import AssistantTrace, AssistantTurn
from app.models.book import Book, BookType, CitationStyle
from app.models.user import User
from app.prompts.assistant.global_system import global_turn_output_instruction
from app.prompts.assistant.startup_system import STARTUP_ASSISTANT_SYSTEM, turn_output_instruction
from app.services.assistant.context_compression_service import ContextCompressionService
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.services.assistant.tool_orchestrator import ToolOrchestrator
from app.services.sources.source_library_service import SourceLibraryService
from app.services.writing.basis_requirement_sync import sync_book_fields_from_basis
from app.services.writing.project_seed import (
    infer_and_apply_book_settings,
    is_provisional_classification,
    mark_classification_source,
    resolve_project_seed,
)
from app.services.writing.writing_basis_service import WritingBasisService
from app.utils.json_llm import parse_llm_json
from app.constants.style_types import StyleType


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


_VALID_STYLES = {s.value for s in StyleType}


def _is_placeholder_title(title: str | None) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if t in {"未命名", "未命名书稿", "新书稿"}:
        return True
    if t.startswith("书稿") and t[2:].isdigit():
        return True
    return False


def _apply_book_settings_patch(book: Book, patch: dict[str, Any]) -> None:
    """Apply assistant book_settings_patch onto Book (shared 书稿设定)."""
    if not patch:
        return
    title = patch.get("title")
    if isinstance(title, str) and title.strip():
        cleaned = title.strip()[:500]
        # 允许：勾选优化书名，或当前仍是占位书名时由助手写入确认后的正式书名
        if book.allow_title_optimization or _is_placeholder_title(book.title):
            if cleaned and not _is_placeholder_title(cleaned):
                book.title = cleaned

    classified = False
    bt = patch.get("book_type")
    if isinstance(bt, str) and bt.strip().lower() in ("nonfiction", "academic"):
        book.book_type = BookType(bt.strip().lower())
        classified = True

    st = patch.get("style_type")
    if isinstance(st, str) and st.strip() in _VALID_STYLES:
        book.style_type = st.strip()
        classified = True

    if classified:
        # Align type↔style if assistant only patched one side
        from app.services.writing.project_seed import _pair_type_and_style

        paired_type, paired_style = _pair_type_and_style(
            book.book_type.value if book.book_type else "",
            book.style_type or "",
            fallback_type=book.book_type or BookType.nonfiction,
            fallback_style=book.style_type or "",
        )
        book.book_type = paired_type
        book.style_type = paired_style
        mark_classification_source(book, "assistant")

    if patch.get("target_audience"):
        book.target_audience = str(patch["target_audience"]).strip()[:500]

    discs = patch.get("disciplines")
    if isinstance(discs, list):
        cleaned = [str(d).strip()[:100] for d in discs if str(d).strip()][:12]
        if cleaned:
            book.disciplines = cleaned
            book.discipline = cleaned[0]

    tags = patch.get("topic_tags")
    if isinstance(tags, list):
        cleaned_tags = [str(t).strip()[:80] for t in tags if str(t).strip()][:40]
        if cleaned_tags:
            book.topic_tags = cleaned_tags

    if patch.get("topic_brief"):
        book.topic_brief = str(patch["topic_brief"]).strip()[:20_000]

    try:
        words = int(patch.get("target_words") or 0)
        if 10_000 <= words <= 500_000:
            book.target_words = words
    except (TypeError, ValueError):
        pass

    cs = patch.get("citation_style")
    if isinstance(cs, str):
        key = cs.strip().lower()
        if key in ("none", "无", "无需"):
            book.citation_style = None
        elif key in {c.value for c in CitationStyle}:
            book.citation_style = CitationStyle(key)


class ProjectAssistantService:
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()
        self._basis = WritingBasisService(db)
        self._sources = SourceLibraryService(db)
        self._tools = ToolOrchestrator(db)
        self._memories = ProjectMemoryService(db)
        self._compression = ContextCompressionService(db)

    def _recent_turns(self, book_id: UUID, limit: int = 10) -> list[AssistantTurn]:
        return (
            self.db.query(AssistantTurn)
            .filter(AssistantTurn.book_id == book_id)
            .order_by(AssistantTurn.created_at.desc())
            .limit(limit)
            .all()[::-1]
        )

    def _build_user_prompt(self, book: Book, message: str, basis_dict: dict[str, Any], *, chapter_index: int | None = None) -> str:
        history = self._compression.recent_turns(book.id, limit=8)
        history_lines = []
        for turn in history:
            history_lines.append(f"用户：{turn.user_message[:1500]}")
            history_lines.append(f"助手：{turn.assistant_message[:1500]}")
        memory_block = self._memories.to_prompt_block(book.id, confirmed_only=True)
        provisional = is_provisional_classification(book)
        bt = book.book_type.value if book.book_type else "nonfiction"
        st = book.style_type or "popular_science"
        class_note = (
            "仍为建书占位默认（大众非虚构/入门科普），必须按创作意图在 book_settings_patch 中改写为合适书类与体裁"
            if provisional
            else "已有分类结果；若本轮意图明显变更可再更新"
        )
        return f"""书名：{book.title}
当前书稿分类：一级={bt}，二级体裁={st}（{class_note}）
当前写作依据：
{json.dumps(basis_dict, ensure_ascii=False)[:6000]}

项目长期记忆（已确认）：
{memory_block or "（无）"}

资料库：
{self._sources.sources_for_prompt(book)}

最近对话：
{chr(10).join(history_lines) if history_lines else "（无）"}
{f"当前章节：第 {chapter_index} 章" if chapter_index is not None else ""}

用户本轮输入：
{message}

{global_turn_output_instruction() if chapter_index is not None else turn_output_instruction()}"""

    def _parse_turn_response(self, raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            raise RuntimeError("模型未返回有效内容，请稍后重试")
        try:
            return parse_llm_json(text)
        except (json.JSONDecodeError, ValueError) as exc:
            if text.startswith("{"):
                raise RuntimeError("助手返回格式异常，请重试") from exc
            return {
                "assistant_message": text[:8000],
                "tool_calls": [],
                "traces": [],
                "memory_updates": [],
                "open_questions": [],
                "basis_patch": {},
            }

    def run_turn(self, book: Book, user: User, message: str, *, chapter_index: int | None = None) -> dict[str, Any]:
        message = message.strip()
        if not message:
            raise ValueError("message required")

        history_chars = self._compression.history_char_count(book.id)
        compressed = self._compression.compress_if_needed(book, user, history_chars=history_chars)

        basis = self._basis.get_draft_or_create(book)
        basis_dict = self._basis.to_dict(basis)
        model = resolve_assistant_model(user)
        raw = self.llm.chat_completion(
            [
                {"role": "system", "content": self._system_prompt(chapter_index)},
                {"role": "user", "content": self._build_user_prompt(book, message, basis_dict, chapter_index=chapter_index)},
            ],
            model=model,
            max_tokens=4000,
            temperature=0.4,
            disable_thinking=True,
        )
        data = self._parse_turn_response(raw)
        assistant_message = str(data.get("assistant_message") or "").strip()
        if not assistant_message:
            raise RuntimeError("模型未返回有效内容，请稍后重试")

        basis_patch = _as_dict(data.get("basis_patch"))
        if basis_patch:
            clean_patch = {k: v for k, v in basis_patch.items() if v is not None}
            if clean_patch:
                self._basis.patch(basis, clean_patch)

        book_settings_patch = _as_dict(data.get("book_settings_patch"))
        if book_settings_patch:
            _apply_book_settings_patch(
                book,
                {k: v for k, v in book_settings_patch.items() if v is not None},
            )

        # Keep Book 书稿设定 in sync with basis so 项目要点 / 高级编辑 stay aligned
        sync_book_fields_from_basis(book, basis)
        self.db.flush()

        # 创作意图已足够、书类仍为占位默认时：服务端按意图推断，避免一直停在大众非虚构
        if chapter_index is None and is_provisional_classification(book):
            seed = resolve_project_seed(book, self.db)
            has_intent = len(seed.strip()) >= 40 or bool(
                (basis.direction or "").strip() or (basis.depth or "").strip() or (basis.scope or "").strip()
            )
            if has_intent:
                try:
                    infer_and_apply_book_settings(book, model, self.db)
                    self.db.flush()
                except Exception:
                    pass

        memory_updates = [
            item for item in _as_list(data.get("memory_updates")) if isinstance(item, dict)
        ]

        tool_calls = _as_list(data.get("tool_calls"))
        executed_tools: list[dict[str, Any]] = []
        if tool_calls:
            executed_tools = self._tools.execute(book, user, tool_calls, chapter_index=chapter_index)

        turn = AssistantTurn(
            book_id=book.id,
            user_message=message,
            assistant_message=assistant_message,
            basis_patch=basis_patch or None,
            tool_calls=executed_tools or tool_calls or None,
        )
        self.db.add(turn)
        self.db.flush()

        if memory_updates:
            self._memories.apply_updates(book.id, memory_updates, source_turn_id=turn.id)

        traces_out: list[AssistantTrace] = []
        for item in _as_list(data.get("traces"))[:8]:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "").strip()
            if not claim:
                continue
            trace = AssistantTrace(
                turn_id=turn.id,
                claim=claim,
                evidence=item.get("evidence"),
                reason_summary=str(item.get("reason_summary") or "").strip() or None,
                confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
            )
            self.db.add(trace)
            traces_out.append(trace)
        self.db.flush()

        open_questions = [str(x).strip() for x in _as_list(data.get("open_questions")) if str(x).strip()]
        if open_questions:
            merged = list(basis.open_questions or [])
            for q in open_questions:
                if q not in merged:
                    merged.append(q)
            basis.open_questions = merged[:20]
            self.db.flush()

        refreshed = self._basis.get_draft(book.id) or basis
        pending_confirmations = [
            r for r in executed_tools if r.get("requires_confirmation")
        ]
        return {
            "turn_id": turn.id,
            "assistant_message": assistant_message,
            "writing_basis": refreshed,
            "traces": traces_out,
            "sources": self._sources.list_sources(book),
            "open_questions": list(refreshed.open_questions or []),
            "memories": self._memories.list_memories(book.id),
            "compressed_memories": compressed,
            "tool_results": executed_tools,
            "pending_confirmations": pending_confirmations,
        }

    def _system_prompt(self, chapter_index: int | None) -> str:
        if chapter_index is not None:
            from app.prompts.assistant.global_system import GLOBAL_ASSISTANT_SYSTEM

            return GLOBAL_ASSISTANT_SYSTEM
        return STARTUP_ASSISTANT_SYSTEM

    def list_turns(self, book_id: UUID, *, page: int = 1, page_size: int = 20) -> list[AssistantTurn]:
        offset = max(page - 1, 0) * page_size
        return (
            self.db.query(AssistantTurn)
            .filter(AssistantTurn.book_id == book_id)
            .order_by(AssistantTurn.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

    def list_traces(self, book_id: UUID, *, turn_id: UUID | None = None) -> list[AssistantTrace]:
        q = self.db.query(AssistantTrace).join(AssistantTurn, AssistantTrace.turn_id == AssistantTurn.id).filter(
            AssistantTurn.book_id == book_id
        )
        if turn_id:
            q = q.filter(AssistantTrace.turn_id == turn_id)
        return q.order_by(AssistantTrace.turn_id.desc()).all()
