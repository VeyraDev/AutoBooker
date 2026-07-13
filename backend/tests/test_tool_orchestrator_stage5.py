"""ToolOrchestrator Stage 5 tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.assistant.tool_orchestrator import ToolOrchestrator


def _book():
    return SimpleNamespace(
        id=uuid4(),
        title="测试书",
        book_type="textbook",
        style_type=None,
        last_literature_query=None,
    )


def _user():
    return SimpleNamespace(id=uuid4())


def test_update_project_understanding_tool():
    db = MagicMock()
    orch = ToolOrchestrator(db)
    book = _book()
    user = _user()
    with patch.object(orch._memories, "upsert_from_update") as upsert:
        upsert.return_value = SimpleNamespace(
            id=uuid4(),
            content="不要营销腔",
            memory_type=SimpleNamespace(value="constraint"),
        )
        results = orch.execute(
            book,
            user,
            [{"name": "update_project_understanding", "arguments": {"content": "不要营销腔", "memory_type": "constraint"}}],
        )
    assert results[0]["ok"] is True
    assert results[0]["panel_hint"] == "memory"


def test_unknown_tool():
    db = MagicMock()
    orch = ToolOrchestrator(db)
    results = orch.execute(_book(), _user(), [{"name": "nonexistent_tool", "arguments": {}}])
    assert results[0]["ok"] is False
    assert results[0]["error"] == "unknown tool"


def test_list_chapter_figures_requires_index():
    db = MagicMock()
    orch = ToolOrchestrator(db)
    results = orch.execute(_book(), _user(), [{"name": "list_chapter_figures", "arguments": {}}])
    assert results[0]["ok"] is False
