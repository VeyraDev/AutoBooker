"""ProjectAssistantService unit tests."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.models.writing_basis import WritingBasis, WritingBasisStatus
from app.services.assistant.project_assistant_service import ProjectAssistantService


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *_args, **_kwargs):
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

    def count(self):
        return len(self._rows)

    def join(self, *_args, **_kwargs):
        return self

    def offset(self, *_args, **_kwargs):
        return self


class _Db:
    def __init__(self):
        self.bases: list[WritingBasis] = []
        self.turns = []
        self.traces = []
        self.added = []

    def query(self, model):
        from app.models.assistant_turn import AssistantTrace, AssistantTurn

        if model is WritingBasis:
            return _Query(self.bases)
        if model is AssistantTurn:
            return _Query(self.turns)
        if model is AssistantTrace:
            return _Query(self.traces)
        if model is SimpleNamespace:
            return _Query([])
        return _Query([])

    def add(self, row):
        self.added.append(row)
        from app.models.assistant_turn import AssistantTrace, AssistantTurn

        if isinstance(row, WritingBasis):
            self.bases.append(row)
        elif isinstance(row, AssistantTurn):
            self.turns.append(row)
        elif isinstance(row, AssistantTrace):
            self.traces.append(row)

    def flush(self):
        return None


class _Llm:
    def __init__(self, payload: dict):
        self.payload = payload

    def chat_completion(self, messages, **_kwargs):
        return json.dumps(self.payload, ensure_ascii=False)


def _book():
    return SimpleNamespace(id=uuid4(), title="AI Marketing", creation_origin=None)


def _user():
    return SimpleNamespace(id=uuid4(), assistant_ai_model=None)


def test_run_turn_applies_basis_patch_and_traces():
    db = _Db()
    svc = ProjectAssistantService(db)  # type: ignore[arg-type]
    svc.llm = _Llm(
        {
            "assistant_message": "你想写一本面向中小商家的实战书，我会避免趋势报告腔。",
            "basis_patch": {
                "direction": "AI 数字营销实战",
                "target_readers": "中小商家",
                "must_avoid": ["趋势报告腔"],
            },
            "traces": [
                {
                    "claim": "本书应偏实战而非趋势报告",
                    "evidence": ["用户说不要趋势报告"],
                    "reason_summary": "用户明确禁令",
                    "confidence": 0.9,
                }
            ],
            "tool_calls": [],
            "open_questions": ["是否有现成案例？"],
        }
    )
    book = _book()
    result = svc.run_turn(book, _user(), "我想写 AI 数字营销实战书，不要趋势报告")
    assert "实战" in result["assistant_message"]
    assert result["writing_basis"].direction == "AI 数字营销实战"
    assert "趋势报告腔" in (result["writing_basis"].must_avoid or [])
    assert len(result["traces"]) == 1
    assert len(db.turns) == 1


def test_parse_turn_response_accepts_plain_text():
    db = _Db()
    svc = ProjectAssistantService(db)  # type: ignore[arg-type]
    data = svc._parse_turn_response("这是助手直接返回的纯文本回复。")
    assert data["assistant_message"] == "这是助手直接返回的纯文本回复。"
