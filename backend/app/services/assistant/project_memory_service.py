"""CRUD and prompt formatting for project memories."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.project_memory import (
    ProjectMemory,
    ProjectMemoryStrength,
    ProjectMemoryType,
)


def _parse_memory_type(value: str) -> ProjectMemoryType:
    try:
        return ProjectMemoryType(str(value).strip())
    except ValueError:
        return ProjectMemoryType.fact


def _parse_strength(value: str) -> ProjectMemoryStrength:
    try:
        return ProjectMemoryStrength(str(value).strip())
    except ValueError:
        return ProjectMemoryStrength.should


_TYPE_LABELS = {
    ProjectMemoryType.fact: "项目事实",
    ProjectMemoryType.decision: "已做决策",
    ProjectMemoryType.constraint: "约束禁令",
    ProjectMemoryType.open_question: "待确认问题",
    ProjectMemoryType.risk: "风险提醒",
}


class ProjectMemoryService:
    def __init__(self, db: Session):
        self.db = db

    def list_memories(self, book_id: UUID) -> list[ProjectMemory]:
        return (
            self.db.query(ProjectMemory)
            .filter(ProjectMemory.book_id == book_id)
            .order_by(ProjectMemory.confirmed.desc(), ProjectMemory.updated_at.desc())
            .all()
        )

    def get_or_none(self, book_id: UUID, memory_id: UUID) -> ProjectMemory | None:
        return (
            self.db.query(ProjectMemory)
            .filter(ProjectMemory.book_id == book_id, ProjectMemory.id == memory_id)
            .first()
        )

    def upsert_from_update(
        self,
        book_id: UUID,
        *,
        content: str,
        memory_type: str = "fact",
        strength: str = "should",
        confirmed: bool = False,
        source_turn_id: UUID | None = None,
    ) -> ProjectMemory:
        content = content.strip()
        if not content:
            raise ValueError("memory content required")
        mtype = _parse_memory_type(memory_type)
        mstrength = _parse_strength(strength)

        existing = (
            self.db.query(ProjectMemory)
            .filter(
                ProjectMemory.book_id == book_id,
                ProjectMemory.content == content,
                ProjectMemory.memory_type == mtype,
            )
            .first()
        )
        if existing:
            existing.strength = mstrength
            existing.confirmed = confirmed or existing.confirmed
            if source_turn_id:
                existing.source_turn_id = source_turn_id
            self.db.flush()
            return existing

        row = ProjectMemory(
            book_id=book_id,
            memory_type=mtype,
            content=content,
            strength=mstrength,
            confirmed=confirmed,
            source_turn_id=source_turn_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def apply_updates(
        self,
        book_id: UUID,
        updates: list[dict[str, Any]],
        *,
        source_turn_id: UUID | None = None,
    ) -> list[ProjectMemory]:
        rows: list[ProjectMemory] = []
        for item in updates:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            rows.append(
                self.upsert_from_update(
                    book_id,
                    content=content,
                    memory_type=str(item.get("memory_type") or "fact"),
                    strength=str(item.get("strength") or "should"),
                    confirmed=bool(item.get("confirmed")),
                    source_turn_id=source_turn_id,
                )
            )
        return rows

    def patch(self, row: ProjectMemory, patch: dict[str, Any]) -> ProjectMemory:
        if patch.get("content") is not None:
            content = str(patch["content"]).strip()
            if not content:
                raise ValueError("content cannot be empty")
            row.content = content
        if patch.get("memory_type") is not None:
            row.memory_type = _parse_memory_type(str(patch["memory_type"]))
        if patch.get("strength") is not None:
            row.strength = _parse_strength(str(patch["strength"]))
        if patch.get("confirmed") is not None:
            row.confirmed = bool(patch["confirmed"])
        self.db.flush()
        return row

    def delete(self, row: ProjectMemory) -> None:
        self.db.delete(row)
        self.db.flush()

    def to_prompt_block(self, book_id: UUID, *, confirmed_only: bool = True) -> str:
        q = self.db.query(ProjectMemory).filter(ProjectMemory.book_id == book_id)
        if confirmed_only:
            q = q.filter(ProjectMemory.confirmed.is_(True))
        rows = q.order_by(ProjectMemory.updated_at.desc()).limit(40).all()
        if not rows:
            return ""

        by_type: dict[ProjectMemoryType, list[str]] = {}
        for row in rows:
            label = _TYPE_LABELS.get(row.memory_type, row.memory_type.value)
            prefix = f"[{row.strength.value}] " if row.strength == ProjectMemoryStrength.must else ""
            by_type.setdefault(row.memory_type, []).append(f"{prefix}{row.content[:500]}")

        parts: list[str] = []
        for mtype in (
            ProjectMemoryType.constraint,
            ProjectMemoryType.decision,
            ProjectMemoryType.fact,
            ProjectMemoryType.risk,
            ProjectMemoryType.open_question,
        ):
            items = by_type.get(mtype)
            if not items:
                continue
            label = _TYPE_LABELS[mtype]
            parts.append(f"【{label}】\n" + "\n".join(f"- {x}" for x in items[:12]))
        return "\n\n".join(parts).strip()
