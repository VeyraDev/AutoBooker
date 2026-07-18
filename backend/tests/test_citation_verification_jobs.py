"""Tests for citation verification background job helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.services.citation_verification_jobs import (
    citation_due_for_scheduled_refresh,
    create_citation_verification_job,
    scheduled_verification_cutoff,
    _progress_pct,
    _requested_ids,
)


def test_progress_pct_handles_empty_and_bounds():
    assert _progress_pct(0, 0) == 100
    assert _progress_pct(1, 3) == 33
    assert _progress_pct(5, 3) == 100


def test_requested_ids_ignores_invalid_values():
    good = uuid4()
    job = SimpleNamespace(requested_citation_ids=[str(good), "bad-id", None])

    assert _requested_ids(job) == [good]


def test_scheduled_cutoff_uses_stale_after_days():
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)

    cutoff = scheduled_verification_cutoff(stale_after_days=14, now=now)

    assert cutoff == now - timedelta(days=14)


def test_scheduled_refresh_due_for_unverified_and_stale_citations():
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    cutoff = now - timedelta(days=30)

    assert citation_due_for_scheduled_refresh(
        SimpleNamespace(verification_status=None, last_verified_at=None),
        cutoff=cutoff,
    )
    assert citation_due_for_scheduled_refresh(
        SimpleNamespace(verification_status="verified", last_verified_at=now - timedelta(days=31)),
        cutoff=cutoff,
    )
    assert not citation_due_for_scheduled_refresh(
        SimpleNamespace(verification_status="needs_verification", last_verified_at=now - timedelta(days=2)),
        cutoff=cutoff,
    )


def test_scheduled_refresh_can_retry_only_unreachable():
    cutoff = datetime(2026, 7, 1, tzinfo=timezone.utc)

    assert citation_due_for_scheduled_refresh(
        SimpleNamespace(verification_status="unreachable", last_verified_at=datetime(2026, 7, 18, tzinfo=timezone.utc)),
        cutoff=cutoff,
        retry_unreachable_only=True,
    )
    assert not citation_due_for_scheduled_refresh(
        SimpleNamespace(verification_status="verified", last_verified_at=datetime(2026, 6, 1, tzinfo=timezone.utc)),
        cutoff=cutoff,
        retry_unreachable_only=True,
    )


def test_create_job_stores_scheduled_options():
    created = []

    class _Query:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class _Db:
        def query(self, _model):
            return _Query()

        def add(self, row):
            created.append(row)

        def flush(self):
            return None

    book_id = uuid4()
    user_id = uuid4()
    citation_id = uuid4()

    job = create_citation_verification_job(
        _Db(),
        book_id=book_id,
        user_id=user_id,
        citation_ids=[citation_id],
        result_options={"scheduled": True, "stale_after_days": 30, "selected_count": 1},
    )

    assert created == [job]
    assert job.book_id == book_id
    assert job.user_id == user_id
    assert job.requested_citation_ids == [str(citation_id)]
    assert job.result_json["retry_unreachable_only"] is False
    assert job.result_json["scheduled"] is True
    assert job.result_json["selected_count"] == 1
