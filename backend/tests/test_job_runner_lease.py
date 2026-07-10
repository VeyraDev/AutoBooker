"""JobRunner lease mutual exclusion (in-memory)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.models.book_job import BookJob, BookJobStatus
from app.services.jobs.job_runner import LeaseService


class _MemJob:
    def __init__(self):
        self.id = uuid.uuid4()
        self.status = BookJobStatus.pending
        self.lease_owner = None
        self.lease_until = None
        self.heartbeat_at = None


class _MemDb:
    def flush(self):
        pass


def test_double_claim_blocks_second_worker():
    job = _MemJob()
    db = _MemDb()
    leases = LeaseService(db)  # type: ignore[arg-type]
    assert leases.try_claim(job, "worker-a") is True
    job.lease_until = datetime.now(timezone.utc) + timedelta(seconds=120)
    assert leases.try_claim(job, "worker-b") is False
