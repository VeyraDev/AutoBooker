"""Dispatch book jobs with DB lease."""

from __future__ import annotations

import logging
import socket
import uuid
from uuid import UUID

from app.database import SessionLocal
from app.models.book_job import BookJob, BookJobStatus
from app.services.auto_book_job import run_auto_book_job
from app.services.jobs.job_runner import JobRunner, LeaseService

logger = logging.getLogger(__name__)


def _worker_id() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


def dispatch_book_job(job_id: UUID) -> None:
    """Claim lease and run auto book job; safe for BackgroundTasks."""
    worker_id = _worker_id()
    db = SessionLocal()
    try:
        job = db.get(BookJob, job_id)
        if not job or job.status not in (BookJobStatus.pending, BookJobStatus.running):
            return
        runner = JobRunner(db)
        if not runner.leases.try_claim(job, worker_id):
            logger.info("book job %s already leased", job_id)
            return
        db.commit()
    finally:
        db.close()

    try:
        run_auto_book_job(job_id, worker_id=worker_id)
    finally:
        db = SessionLocal()
        try:
            job = db.get(BookJob, job_id)
            if job:
                LeaseService(db).release(job, worker_id)
                db.commit()
        finally:
            db.close()
