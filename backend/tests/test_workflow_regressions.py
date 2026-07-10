import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.models.book import BookStatus, CitationStyle
from app.models.book_job import BookJob, BookJobStatus
from app.routers import book_jobs as book_jobs_router
from app.routers.outline import _mark_auto_job_writing_started
from app.services import book_service


class _JobQuery:
    def __init__(self, existing):
        self.existing = existing

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.existing

    def order_by(self, *_args, **_kwargs):
        return self


class _JobDb:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.commits = 0

    def query(self, *_args, **_kwargs):
        return _JobQuery(self.existing)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid4()

    def refresh(self, _value):
        return None

    def flush(self):
        return None


def test_retry_replaces_a_job_interrupted_by_process_restart(monkeypatch):
    book_id = uuid4()
    user_id = uuid4()
    existing = BookJob(
        id=uuid4(),
        book_id=book_id,
        user_id=user_id,
        status=BookJobStatus.running,
        checkpoint_json={"worker_pid": os.getpid() + 100_000},
    )
    book = SimpleNamespace(id=book_id, status=BookStatus.setup)
    user = SimpleNamespace(id=user_id)
    db = _JobDb(existing)

    monkeypatch.setattr(
        book_jobs_router.book_service,
        "get_book_or_404",
        lambda *_args, **_kwargs: book,
    )
    monkeypatch.setattr(book_jobs_router, "build_job_detail", lambda *_args: {})

    result = book_jobs_router.start_auto_generate_for_book(
        book_id,
        BackgroundTasks(),
        user,
        db,
    )

    assert existing.status == BookJobStatus.failed
    assert result.status == BookJobStatus.pending.value
    assert len(db.added) == 1
    assert db.added[0] is not existing
    assert book.status == BookStatus.auto_generating


def test_atomic_one_click_endpoint_requires_confirmed_intake():
    user = SimpleNamespace(id=uuid4())
    db = _JobDb()
    body = book_jobs_router.AutoGenerateIn(
        title="功能测试书稿",
        book_type="nonfiction",
        style_type="popular_science",
    )

    with pytest.raises(HTTPException) as exc:
        book_jobs_router.start_auto_generate(
            body,
            BackgroundTasks(),
            user,
            db,
        )

    assert exc.value.status_code == 400
    assert "确认项目输入" in exc.value.detail
    assert db.added == []


def test_starting_editor_persists_auto_writing_checkpoint():
    job = BookJob(
        id=uuid4(),
        book_id=uuid4(),
        user_id=uuid4(),
        status=BookJobStatus.completed,
        checkpoint_json={"ready_for_editor": True, "writing_started": False},
    )
    db = _JobDb(job)

    _mark_auto_job_writing_started(db, job.book_id)

    assert job.checkpoint_json["writing_started"] is True


def test_book_update_coerces_json_enum_values_before_citation_sync(monkeypatch):
    book = SimpleNamespace(
        citation_style=None,
        status=BookStatus.setup,
        disciplines=None,
        discipline=None,
    )
    db = _JobDb()
    refreshed = []

    monkeypatch.setattr(
        "app.services.citation_nodes.refresh_book_citation_rendering",
        lambda _db, value: refreshed.append(value.citation_style),
    )
    monkeypatch.setattr(
        "app.services.citation_service.sync_book_bibliography",
        lambda *_args, **_kwargs: None,
    )

    result = book_service.update_book(
        book,
        {"citation_style": "apa", "status": "setup"},
        db,
    )

    assert result.citation_style == CitationStyle.apa
    assert result.status == BookStatus.setup
    assert refreshed == [CitationStyle.apa]
