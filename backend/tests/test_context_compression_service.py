"""ContextCompressionService tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.assistant.context_compression_service import (
    COMPRESS_EVERY_N_TURNS,
    ContextCompressionService,
)


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def limit(self, n):
        self._rows = self._rows[-n:]
        return self

    def all(self):
        return list(self._rows)

    def count(self):
        return len(self._rows)


class _Db:
    def __init__(self, turn_count: int):
        self.turn_count = turn_count
        self.memories = []

    def query(self, model):
        from app.models.assistant_turn import AssistantTurn
        from app.models.project_memory import ProjectMemory

        if model is AssistantTurn:
            turns = [
                SimpleNamespace(
                    id=uuid4(),
                    user_message=f"u{i}",
                    assistant_message=f"a{i}",
                )
                for i in range(self.turn_count)
            ]
            return _Query(turns)
        if model is ProjectMemory:
            return _Query(self.memories)
        return _Query([])

    def add(self, row):
        self.memories.append(row)

    def flush(self):
        return None


def test_should_compress_every_n_turns():
    db = _Db(COMPRESS_EVERY_N_TURNS)
    svc = ContextCompressionService(db)
    assert svc.should_compress(uuid4()) is True


def test_should_not_compress_below_threshold():
    db = _Db(5)
    svc = ContextCompressionService(db)
    assert svc.should_compress(uuid4(), history_chars=100) is False
