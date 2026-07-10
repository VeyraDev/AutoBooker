"""Database-backed job lease and runner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book_job import BookJob, BookJobStatus


class LeaseService:
    LEASE_SECONDS = 120

    def __init__(self, db: Session):
        self.db = db

    def try_claim(self, job: BookJob, worker_id: str) -> bool:
        now = datetime.now(timezone.utc)
        if job.lease_until and job.lease_until > now and job.lease_owner and job.lease_owner != worker_id:
            return False
        job.lease_owner = worker_id
        job.lease_until = now + timedelta(seconds=self.LEASE_SECONDS)
        job.heartbeat_at = now
        if job.status == BookJobStatus.pending:
            job.status = BookJobStatus.running
        self.db.flush()
        return True

    def heartbeat(self, job: BookJob, worker_id: str) -> None:
        if job.lease_owner != worker_id:
            return
        now = datetime.now(timezone.utc)
        job.heartbeat_at = now
        job.lease_until = now + timedelta(seconds=self.LEASE_SECONDS)
        self.db.flush()

    def release(self, job: BookJob, worker_id: str) -> None:
        if job.lease_owner != worker_id:
            return
        job.lease_owner = None
        job.lease_until = None
        self.db.flush()


class JobRunner:
    def __init__(self, db: Session):
        self.db = db
        self.leases = LeaseService(db)

    def claim_next_book_job(self, worker_id: str) -> BookJob | None:
        now = datetime.now(timezone.utc)
        job = (
            self.db.query(BookJob)
            .filter(
                BookJob.status.in_([BookJobStatus.pending, BookJobStatus.running]),
            )
            .order_by(BookJob.created_at.asc())
            .first()
        )
        if not job:
            return None
        if job.lease_until and job.lease_until > now and job.lease_owner and job.lease_owner != worker_id:
            return None
        if self.leases.try_claim(job, worker_id):
            self.db.commit()
            return job
        return None
