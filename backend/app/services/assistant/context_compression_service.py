"""Compress long assistant conversations into ProjectMemory."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.providers import resolve_assistant_model
from app.models.assistant_turn import AssistantTurn
from app.models.book import Book
from app.models.user import User
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.utils.json_llm import parse_llm_json

COMPRESS_EVERY_N_TURNS = 20
KEEP_RECENT_TURNS = 8
HISTORY_CHAR_THRESHOLD = 12000


class ContextCompressionService:
    def __init__(self, db: Session):
        self.db = db
        self._memories = ProjectMemoryService(db)
        self._llm = LLMClient()

    def turn_count(self, book_id: UUID) -> int:
        return self.db.query(AssistantTurn).filter(AssistantTurn.book_id == book_id).count()

    def should_compress(self, book_id: UUID, *, history_chars: int = 0) -> bool:
        count = self.turn_count(book_id)
        if count >= COMPRESS_EVERY_N_TURNS and count % COMPRESS_EVERY_N_TURNS == 0:
            return True
        return history_chars >= HISTORY_CHAR_THRESHOLD

    def recent_turns(self, book_id: UUID, limit: int = KEEP_RECENT_TURNS) -> list[AssistantTurn]:
        rows = (
            self.db.query(AssistantTurn)
            .filter(AssistantTurn.book_id == book_id)
            .order_by(AssistantTurn.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(rows))

    def turns_to_compress(self, book_id: UUID, keep_recent: int = KEEP_RECENT_TURNS) -> list[AssistantTurn]:
        all_turns = (
            self.db.query(AssistantTurn)
            .filter(AssistantTurn.book_id == book_id)
            .order_by(AssistantTurn.created_at.asc())
            .all()
        )
        if len(all_turns) <= keep_recent:
            return []
        return all_turns[: len(all_turns) - keep_recent]

    def _format_turns(self, turns: list[AssistantTurn]) -> str:
        lines: list[str] = []
        for turn in turns:
            lines.append(f"用户：{turn.user_message[:1200]}")
            lines.append(f"助手：{turn.assistant_message[:1200]}")
        return "\n".join(lines)

    def compress_if_needed(
        self,
        book: Book,
        user: User,
        *,
        history_chars: int = 0,
    ) -> list[dict[str, Any]]:
        if not self.should_compress(book.id, history_chars=history_chars):
            return []
        old_turns = self.turns_to_compress(book.id)
        if not old_turns:
            return []
        transcript = self._format_turns(old_turns[-30:])
        if not transcript.strip():
            return []

        model = resolve_assistant_model(user)
        raw = self._llm.chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "你是项目记忆压缩器。将对话历史提炼为结构化长期记忆。"
                        "只输出 JSON：{\"memory_updates\":[{\"memory_type\":\"decision|constraint|fact|open_question|risk\","
                        "\"content\":\"...\",\"strength\":\"must|should|preference\",\"confirmed\":true|false}]}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"书名：{book.title}\n\n对话历史：\n{transcript[:10000]}",
                },
            ],
            model=model,
            max_tokens=2000,
            temperature=0.2,
        )
        data = parse_llm_json(raw)
        updates = data.get("memory_updates") if isinstance(data.get("memory_updates"), list) else []
        source_turn_id = old_turns[-1].id if old_turns else None
        rows = self._memories.apply_updates(book.id, updates, source_turn_id=source_turn_id)
        return [
            {
                "memory_type": r.memory_type.value,
                "content": r.content,
                "strength": r.strength.value,
                "confirmed": r.confirmed,
            }
            for r in rows
        ]

    def history_char_count(self, book_id: UUID, limit: int = KEEP_RECENT_TURNS) -> int:
        turns = self.recent_turns(book_id, limit=limit)
        return len(self._format_turns(turns))
