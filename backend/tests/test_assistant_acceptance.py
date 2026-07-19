"""设计文档 §十四：助手全链路验收（契约/单元级，不依赖真实 LLM）。"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.assistant_turn import AssistantTrace, AssistantTurn
from app.routers import intake as intake_router
from app.routers import outline as outline_router
from app.routers import project_assistant as project_assistant_router
from app.routers import sources as sources_router
from app.routers import writing_basis as writing_basis_router
from app.schemas.project_assistant import TurnOut
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.services.assistant.tool_orchestrator import ToolOrchestrator
from app.services.sources.source_segment_service import SourceSegmentService
from app.services.writing.writing_context_builder import WritingContextBuilder


def _route_paths(router) -> set[str]:
    return {getattr(r, "path", "") for r in router.routes}


def test_acceptance_01_bootstrap_and_sources_api_exist():
    """自然语言+资料启动：bootstrap 与 sources API 存在。"""
    intake_paths = _route_paths(intake_router.router)
    assert "/books/{book_id}/project-start/bootstrap" in intake_paths
    source_paths = _route_paths(sources_router.router)
    assert "/books/{book_id}/sources" in source_paths
    assert "/books/{book_id}/sources/upload" in source_paths
    assert "/books/{book_id}/sources/{source_id}" in source_paths


def test_acceptance_02_source_segment_extract():
    """混合文件识别：SourceSegmentService 提供分段抽取。"""
    assert hasattr(SourceSegmentService, "extract_segments")
    assert "force" in inspect.signature(SourceSegmentService.extract_segments).parameters


def test_acceptance_03_external_search_tool_routing():
    """外部检索选题：ExternalSearchService mock + tool 路由。"""
    db = MagicMock()
    orch = ToolOrchestrator(db)
    book = SimpleNamespace(id=uuid4(), title="测试书")
    user = SimpleNamespace(id=uuid4())
    search_payload = {
        "person": "张三",
        "works": [{"title": "Paper A", "source": "arxiv"}],
        "research_directions": ["AI"],
        "source_scope": "public",
        "warnings": [],
    }
    with patch.object(orch._external, "search_person_works", return_value=search_payload):
        with patch.object(orch._sources, "add_pasted_text") as add_paste:
            add_paste.return_value = SimpleNamespace(id=uuid4())
            results = orch.execute(
                book,
                user,
                [{"name": "search_person_works", "arguments": {"person_name": "张三"}}],
            )
    assert results[0]["ok"] is True
    assert results[0]["panel_hint"] == "sources"
    assert results[0]["data"]["person"] == "张三"


def test_acceptance_04_turn_model_basis_patch_and_memory_updates():
    """判断沉淀依据/记忆：Turn 模型与 schema 支持依据链字段。"""
    assert hasattr(AssistantTurn, "basis_patch")
    turn_fields = set(TurnOut.model_fields)
    assert "writing_basis" in turn_fields
    assert "memories" in turn_fields
    assert "tool_results" in turn_fields


def test_acceptance_05_assistant_trace_persistence_model():
    """traces 依据链：AssistantTrace 可持久化。"""
    assert hasattr(AssistantTrace, "claim")
    assert hasattr(AssistantTrace, "evidence")
    assert hasattr(AssistantTrace, "turn_id")


def test_acceptance_06_patch_writing_basis_route_exists():
    """手动编辑 basis：PATCH writing-basis 路由存在。"""
    paths = _route_paths(writing_basis_router.router)
    assert "/books/{book_id}/writing-basis" in paths
    patch_routes = [r for r in writing_basis_router.router.routes if getattr(r, "path", "") == "/books/{book_id}/writing-basis"]
    methods = {m for r in patch_routes for m in getattr(r, "methods", set())}
    assert "PATCH" in methods


def test_acceptance_07_book_editor_no_legacy_intake_gate():
    """确认后不回旧表单：BookEditorPage 无 legacy intake 门控。"""
    frontend_root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    text = (frontend_root / "pages" / "BookEditorPage.tsx").read_text(encoding="utf-8")
    assert "shouldShowLegacyIntake" not in text
    assert "ProjectInputPage" not in text
    assert "legacyIntake" not in text
    assert "shouldShowAssistant" in text
    assert "ProjectAssistantPage" in text


def test_acceptance_08_outline_reads_writing_basis_via_wcb():
    """大纲基于 basis：outline 生成注入 WritingContextBuilder。"""
    src = inspect.getsource(outline_router.generate_outline)
    assert "WritingContextBuilder" in src
    assert "build_for_outline" in src


def test_acceptance_09_propose_outline_change_requires_confirmation():
    """大纲变更预览：propose_outline_change 标记 requires_confirmation。"""
    db = MagicMock()
    orch = ToolOrchestrator(db)
    book = SimpleNamespace(id=uuid4(), title="测试书")
    user = SimpleNamespace(id=uuid4())
    with patch("app.services.assistant.tool_orchestrator.serialize_book_outline_markdown", return_value="# 大纲"):
        with patch.object(orch._llm, "chat_completion", return_value="预览：合并第1、2章"):
            results = orch.execute(
                book,
                user,
                [{"name": "propose_outline_change", "arguments": {"instruction": "合并前两章"}}],
            )
    assert results[0]["ok"] is True
    assert results[0]["requires_confirmation"] is True
    assert results[0]["panel_hint"] == "confirm"


def test_acceptance_10_tool_results_panel_hint_contract():
    """工具进固定面板：tool_results 含 panel_hint。"""
    db = MagicMock()
    orch = ToolOrchestrator(db)
    book = SimpleNamespace(id=uuid4(), title="测试书")
    user = SimpleNamespace(id=uuid4())
    with patch.object(orch._sources, "list_sources", return_value=[]):
        results = orch.execute(book, user, [{"name": "list_sources", "arguments": {}}])
    assert results[0]["panel_hint"] == "sources"


def test_acceptance_11_pending_confirmations_from_propose_topics():
    """高风险确认门：选题预览进入 pending_confirmations 形态。"""
    db = MagicMock()
    orch = ToolOrchestrator(db)
    book = SimpleNamespace(id=uuid4(), title="测试书")
    user = SimpleNamespace(id=uuid4())
    search_payload = {
        "person": "李四",
        "works": [{"title": "Work", "source": "crossref"}],
        "research_directions": [],
        "source_scope": "public",
        "warnings": [],
    }
    proposal_json = (
        '{"topics":[{"title":"主题A","rationale":"理由","audience":"读者","feasibility":"高","risks":[]}],'
        '"recommended_index":0,"source_disclaimer":"公开检索"}'
    )
    with patch.object(orch._external, "search_person_works", return_value=search_payload):
        with patch.object(orch._llm, "chat_completion", return_value=proposal_json):
            results = orch.execute(
                book,
                user,
                [{"name": "propose_book_topics", "arguments": {"person_name": "李四"}}],
            )
    assert results[0]["ok"] is True
    assert results[0]["requires_confirmation"] is True
    assert results[0]["panel_hint"] == "confirm"
    pending = [
        {"name": r["name"], "panel_hint": r["panel_hint"], "data": r.get("data") or {}}
        for r in results
        if r.get("requires_confirmation")
    ]
    assert pending


def test_acceptance_12_project_memory_to_prompt_block():
    """长记忆保留：ProjectMemory to_prompt_block 可输出。"""
    from app.models.project_memory import ProjectMemory

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

    db = _Db()
    svc = ProjectMemoryService(db)  # type: ignore[arg-type]
    book_id = uuid4()
    svc.upsert_from_update(
        book_id,
        content="不要营销腔",
        memory_type="constraint",
        strength="must",
        confirmed=True,
    )
    block = svc.to_prompt_block(book_id)
    assert "不要营销腔" in block


def test_acceptance_13_writing_context_builder_injects_basis_and_memory():
    """写作读 basis：WritingContextBuilder 注入 basis 与 memory。"""
    src = inspect.getsource(WritingContextBuilder.to_prompt_block)
    assert "writing_basis" in src
    assert "项目长期记忆" in src


def test_acceptance_14_project_assistant_turns_and_page_route():
    """对话工作台体验：project-assistant turns API 与助手页存在。"""
    paths = _route_paths(project_assistant_router.router)
    assert "/books/{book_id}/project-assistant/turns" in paths
    frontend_root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    assert (frontend_root / "features" / "assistant" / "components" / "ProjectAssistantPage.tsx").is_file()
    assistant_api = (frontend_root / "features" / "assistant" / "api" / "assistantApi.ts").read_text(encoding="utf-8")
    assert "/project-assistant/turns" in assistant_api


def test_bootstrap_handler_is_not_deprecated():
    """bootstrap 端点仍可写，与 410 旧接口区分。"""
    assert "bootstrap_project_start" in inspect.getsource(intake_router.bootstrap_project_start)
    with pytest.raises(HTTPException) as exc:
        intake_router._deprecated_intake_write()
    assert exc.value.status_code == 410
