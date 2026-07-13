"""ProjectMemoryService tests."""

from __future__ import annotations

from uuid import uuid4

from app.models.project_memory import ProjectMemory, ProjectMemoryStrength, ProjectMemoryType
from app.services.assistant.project_memory_service import ProjectMemoryService


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)
        self._filters = []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Db:
    def __init__(self):
        self.rows: list[ProjectMemory] = []

    def query(self, model):
        if model is ProjectMemory:
            return _Query(self.rows)
        return _Query([])

    def add(self, row):
        self.rows.append(row)

    def flush(self):
        return None

    def delete(self, row):
        self.rows.remove(row)


def test_upsert_and_prompt_block():
    db = _Db()
    svc = ProjectMemoryService(db)
    book_id = uuid4()
    row = svc.upsert_from_update(
        book_id,
        content="不要营销腔",
        memory_type="constraint",
        strength="must",
        confirmed=True,
    )
    assert row.content == "不要营销腔"
    assert row.memory_type == ProjectMemoryType.constraint
    assert row.strength == ProjectMemoryStrength.must
    block = svc.to_prompt_block(book_id, confirmed_only=True)
    assert "不要营销腔" in block
    assert "约束禁令" in block


def test_apply_updates_dedupes():
    db = _Db()
    svc = ProjectMemoryService(db)
    book_id = uuid4()
    svc.apply_updates(
        book_id,
        [
            {"content": "保留原大纲", "memory_type": "decision", "confirmed": True},
            {"content": "保留原大纲", "memory_type": "decision", "confirmed": True},
        ],
    )
    assert len(db.rows) == 1
