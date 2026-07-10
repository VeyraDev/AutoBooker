"""Unified job progress writes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book_job import BookJob, BookJobStatus, BookJobStep


def patch_book_job(
    db: Session,
    job: BookJob,
    *,
    step: BookJobStep | None = None,
    pct: int | None = None,
    status: BookJobStatus | None = None,
    error: str | None = None,
    checkpoint: dict | None = None,
) -> None:
    if step is not None:
        job.current_step = step
    if pct is not None:
        job.progress_pct = pct
    if status is not None:
        job.status = status
        if status in (BookJobStatus.completed, BookJobStatus.failed, BookJobStatus.cancelled):
            job.finished_at = datetime.now(timezone.utc)
    if error is not None:
        job.error_message = error
    if checkpoint is not None:
        merged = dict(job.checkpoint_json or {})
        merged.update(checkpoint)
        job.checkpoint_json = merged
    db.flush()


def mark_book_job_running(db: Session, job_id: UUID, worker_id: str) -> BookJob | None:
    job = db.get(BookJob, job_id)
    if not job or job.status not in (BookJobStatus.pending, BookJobStatus.running):
        return None
    from app.services.jobs.job_runner import LeaseService

    if not LeaseService(db).try_claim(job, worker_id):
        return None
    db.commit()
    return job
