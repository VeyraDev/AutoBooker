"""重构验收：流程可运行性与模块集成（不依赖 LLM/DB 迁移）。"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.models.book import BookStatus
from app.models.book_job import BookJob, BookJobStatus
from app.routers import book_jobs as book_jobs_router
from app.schemas.book_job import AutoGenerateIn
from app.services.writing.writing_context_builder import WritingContextBuilder


def test_refactor_modules_import():
    for mod in (
        "app.services.assets.asset_resolver",
        "app.services.jobs.book_job_dispatch",
        "app.services.review_stage.publication_standard_review",
        "app.services.review_stage.writing_quality_aggregator",
        "app.models.generation_context_snapshot",
    ):
        importlib.import_module(mod)


def test_deprecated_pipeline_modules_removed():
    backend_root = Path(__file__).resolve().parents[1]
    removed = [
        backend_root / "app/services/figure_generate.py",
        backend_root / "app/services/section_assembler.py",
        backend_root / "app/agents/figure_classifier_agent.py",
        backend_root / "app/services/figure_render",
    ]
    assert [str(p) for p in removed if p.exists()] == []

    source_files = list((backend_root / "app").rglob("*.py"))
    forbidden_imports = (
        "app.services.figure_generate",
        "app.services.section_assembler",
        "app.agents.figure_classifier_agent",
        "app.services.figure_render",
    )
    offenders: list[str] = []
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden_imports):
            offenders.append(str(path.relative_to(backend_root)))
    assert offenders == []


def test_wcb_auto_progress_allows_legacy_book_without_creation_origin():
    class _Db:
        def query(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def first(self):
            return SimpleNamespace(creation_origin=None)

    wcb = WritingContextBuilder(_Db())  # type: ignore[arg-type]
    assert wcb.auto_progress_allowed(uuid4()) is True


def test_book_job_start_without_creation_origin_does_not_gate(monkeypatch):
    book_id = uuid4()
    user_id = uuid4()
    existing = BookJob(
        id=uuid4(),
        book_id=book_id,
        user_id=user_id,
        status=BookJobStatus.running,
        checkpoint_json={"worker_pid": 999999},
    )
    book = SimpleNamespace(id=book_id, status=BookStatus.setup)
    user = SimpleNamespace(id=user_id)

    class _Db:
        def query(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def first(self):
            return existing

        def order_by(self, *_a, **_k):
            return self

        def add(self, _v):
            pass

        def commit(self):
            pass

        def refresh(self, _v):
            pass

    monkeypatch.setattr(book_jobs_router.book_service, "get_book_or_404", lambda *_a, **_k: book)
    monkeypatch.setattr(book_jobs_router, "build_job_detail", lambda *_a, **_k: {})
    result = book_jobs_router.start_auto_generate_for_book(book_id, BackgroundTasks(), user, _Db())
    assert result.status in (BookJobStatus.pending.value, BookJobStatus.running.value, BookJobStatus.failed.value)


def test_new_auto_generate_endpoint_requires_confirmed_intake_flow():
    with pytest.raises(HTTPException) as exc:
        book_jobs_router.start_auto_generate(
            AutoGenerateIn(title="Bypass attempt", book_type="nonfiction", style_type="popular_science"),
            BackgroundTasks(),
            SimpleNamespace(id=uuid4()),
            SimpleNamespace(),
        )

    assert exc.value.status_code == 400
    assert "确认项目输入" in str(exc.value.detail)


def test_assets_compat_static_default_off():
    from app.config import settings

    assert settings.ASSETS_COMPAT_STATIC is False


def test_review_stage_submodules_export_public_api():
    from app.services.review_stage import (
        content_risk_reviewer,
        copyediting_scanner,
        export_structure_reviewer,
        input_alignment_reviewer,
    )

    assert hasattr(content_risk_reviewer, "ContentRiskReviewer")
    assert hasattr(copyediting_scanner, "CopyeditingScanner")
    assert hasattr(export_structure_reviewer, "ExportStructureReviewer")
    assert hasattr(input_alignment_reviewer, "InputAlignmentReviewer")
