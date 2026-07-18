"""Background citation verification job runner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.citation import Citation
from app.models.citation_verification_job import CitationVerificationJob, CitationVerificationJobStatus
from app.services.citation_verification import VerifyCitation, refresh_citation_verification, verify_citation_with_public_sources

MAX_JOB_CITATIONS = 500
DEFAULT_SCHEDULED_STALE_AFTER_DAYS = 30
DEFAULT_SCHEDULED_LIMIT = 100


def get_active_citation_verification_job(
    db: Session,
    *,
    book_id: UUID,
) -> CitationVerificationJob | None:
    return (
        db.query(CitationVerificationJob)
        .filter(
            CitationVerificationJob.book_id == book_id,
            CitationVerificationJob.status.in_(
                [
                    CitationVerificationJobStatus.pending.value,
                    CitationVerificationJobStatus.running.value,
                ]
            ),
        )
        .order_by(CitationVerificationJob.created_at.desc())
        .first()
    )


def create_citation_verification_job(
    db: Session,
    *,
    book_id: UUID,
    user_id: UUID,
    citation_ids: list[UUID] | None = None,
    retry_unreachable_only: bool = False,
    result_options: dict[str, Any] | None = None,
) -> CitationVerificationJob:
    existing = get_active_citation_verification_job(db, book_id=book_id)
    if existing:
        return existing
    options = {"retry_unreachable_only": retry_unreachable_only}
    if result_options:
        options.update(result_options)
    job = CitationVerificationJob(
        book_id=book_id,
        user_id=user_id,
        status=CitationVerificationJobStatus.pending.value,
        requested_citation_ids=[str(cid) for cid in citation_ids] if citation_ids else None,
        result_json=options,
    )
    db.add(job)
    db.flush()
    return job


def select_due_citation_ids_for_verification(
    db: Session,
    *,
    book_id: UUID,
    stale_after_days: int = DEFAULT_SCHEDULED_STALE_AFTER_DAYS,
    limit: int = DEFAULT_SCHEDULED_LIMIT,
    include_unverified: bool = True,
    retry_unreachable_only: bool = False,
    now: datetime | None = None,
) -> list[UUID]:
    cutoff = scheduled_verification_cutoff(stale_after_days=stale_after_days, now=now)
    query = db.query(Citation).filter(Citation.book_id == book_id)
    if retry_unreachable_only:
        query = query.filter(Citation.verification_status == "unreachable")
    else:
        conditions = [Citation.last_verified_at < cutoff]
        if include_unverified:
            conditions.extend(
                [
                    Citation.last_verified_at.is_(None),
                    Citation.verification_status.is_(None),
                ]
            )
        query = query.filter(or_(*conditions))
    rows = (
        query.order_by(Citation.last_verified_at.asc().nullsfirst(), Citation.created_at.desc())
        .limit(max(1, min(MAX_JOB_CITATIONS, limit)))
        .all()
    )
    return [row.id for row in rows]


def create_due_citation_verification_job(
    db: Session,
    *,
    book_id: UUID,
    user_id: UUID,
    stale_after_days: int = DEFAULT_SCHEDULED_STALE_AFTER_DAYS,
    limit: int = DEFAULT_SCHEDULED_LIMIT,
    include_unverified: bool = True,
    retry_unreachable_only: bool = False,
    now: datetime | None = None,
) -> tuple[CitationVerificationJob | None, int, str | None]:
    existing = get_active_citation_verification_job(db, book_id=book_id)
    if existing:
        return existing, 0, "active_job_exists"
    citation_ids = select_due_citation_ids_for_verification(
        db,
        book_id=book_id,
        stale_after_days=stale_after_days,
        limit=limit,
        include_unverified=include_unverified,
        retry_unreachable_only=retry_unreachable_only,
        now=now,
    )
    if not citation_ids:
        return None, 0, "no_due_citations"
    job = create_citation_verification_job(
        db,
        book_id=book_id,
        user_id=user_id,
        citation_ids=citation_ids,
        retry_unreachable_only=retry_unreachable_only,
        result_options={
            "scheduled": True,
            "stale_after_days": stale_after_days,
            "include_unverified": include_unverified,
            "selected_count": len(citation_ids),
            "limit": max(1, min(MAX_JOB_CITATIONS, limit)),
        },
    )
    return job, len(citation_ids), None


def scheduled_verification_cutoff(
    *,
    stale_after_days: int = DEFAULT_SCHEDULED_STALE_AFTER_DAYS,
    now: datetime | None = None,
) -> datetime:
    base = _as_utc(now or datetime.now(timezone.utc))
    return base - timedelta(days=max(1, stale_after_days))


def citation_due_for_scheduled_refresh(
    citation: Any,
    *,
    cutoff: datetime,
    include_unverified: bool = True,
    retry_unreachable_only: bool = False,
) -> bool:
    status_value = getattr(citation, "verification_status", None)
    status = str(status_value) if status_value else ""
    if retry_unreachable_only:
        return status == "unreachable"
    last_verified_at = getattr(citation, "last_verified_at", None)
    if include_unverified and (not status or last_verified_at is None):
        return True
    if last_verified_at is None:
        return False
    return _as_utc(last_verified_at) < _as_utc(cutoff)


def run_citation_verification_job(
    job_id: UUID,
    *,
    verifier: VerifyCitation | None = None,
) -> None:
    db = SessionLocal()
    try:
        job = db.get(CitationVerificationJob, job_id)
        if not job or job.status not in {
            CitationVerificationJobStatus.pending.value,
            CitationVerificationJobStatus.running.value,
        }:
            return
        _patch_job(db, job, status=CitationVerificationJobStatus.running.value, progress_pct=0)
        db.commit()
        rows = _job_citations(db, job)
        total = len(rows)
        status_counts: dict[str, int] = {}
        _patch_job(db, job, total_count=total, progress_pct=100 if total == 0 else 0)
        if total == 0:
            _patch_job(
                db,
                job,
                status=CitationVerificationJobStatus.completed.value,
                result_json={**_result_options(job), "status_counts": status_counts},
                finished_at=datetime.now(timezone.utc),
            )
            db.commit()
            return
        runner = verifier or verify_citation_with_public_sources
        succeeded = 0
        failed = 0
        for index, citation in enumerate(rows, start=1):
            result = refresh_citation_verification(citation, verifier=runner)
            status = str(result.get("verification_status") or "needs_verification")
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == "unreachable":
                failed += 1
            else:
                succeeded += 1
            _patch_job(
                db,
                job,
                processed_count=index,
                succeeded_count=succeeded,
                failed_count=failed,
                progress_pct=_progress_pct(index, total),
                result_json={
                    **_result_options(job),
                    "status_counts": status_counts,
                    "last_citation_id": str(citation.id),
                },
            )
            db.commit()
        _patch_job(
            db,
            job,
            status=CitationVerificationJobStatus.completed.value,
            progress_pct=100,
            result_json={**_result_options(job), "status_counts": status_counts},
            finished_at=datetime.now(timezone.utc),
        )
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive job boundary
        db.rollback()
        job = db.get(CitationVerificationJob, job_id)
        if job:
            _patch_job(
                db,
                job,
                status=CitationVerificationJobStatus.failed.value,
                error_message=f"{exc.__class__.__name__}: {exc}",
                finished_at=datetime.now(timezone.utc),
            )
            db.commit()
    finally:
        db.close()


def _job_citations(db: Session, job: CitationVerificationJob) -> list[Citation]:
    query = db.query(Citation).filter(Citation.book_id == job.book_id)
    ids = _requested_ids(job)
    if ids:
        query = query.filter(Citation.id.in_(ids))
    if _result_options(job).get("retry_unreachable_only"):
        query = query.filter(Citation.verification_status == "unreachable")
    return query.order_by(Citation.created_at.desc()).limit(MAX_JOB_CITATIONS).all()


def _requested_ids(job: CitationVerificationJob) -> list[UUID]:
    raw = job.requested_citation_ids if isinstance(job.requested_citation_ids, list) else []
    out: list[UUID] = []
    for item in raw:
        try:
            out.append(UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return out


def _result_options(job: CitationVerificationJob) -> dict[str, Any]:
    return dict(job.result_json or {})


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _progress_pct(processed: int, total: int) -> int:
    if total <= 0:
        return 100
    return max(0, min(100, round(processed * 100 / total)))


def _patch_job(db: Session, job: CitationVerificationJob, **values: Any) -> None:
    for key, value in values.items():
        if value is not None:
            setattr(job, key, value)
    db.flush()
