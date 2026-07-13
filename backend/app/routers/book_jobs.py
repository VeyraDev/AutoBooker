"""一键生成书稿 Job API。"""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.book import BookStatus
from app.models.book_job import BookJob, BookJobStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.book_job import AutoGenerateIn, BookJobDetailOut, BookJobOut
from app.services import book_service
from app.services.jobs.book_job_dispatch import dispatch_book_job
from app.services.auto_book_job_progress import build_job_detail, patch_job_checkpoint

router = APIRouter(prefix="/book-jobs", tags=["book-jobs"])


def _reconcile_job_worker(db: Session, job: BookJob) -> None:
    """BackgroundTasks 随进程重启而消失；若 Job lease 已过期则视为可重试。"""
    if job.status not in (BookJobStatus.pending, BookJobStatus.running):
        return
    from datetime import datetime, timezone

    ck = dict(job.checkpoint_json or {})
    worker_id = ck.get("worker_id")
    if worker_id and job.lease_until and job.lease_until < datetime.now(timezone.utc):
        job.lease_owner = None
        job.lease_until = None
        db.commit()
        return
    worker_pid = ck.get("worker_pid")
    if worker_pid is None:
        return
    if int(worker_pid) == os.getpid():
        return
    job.status = BookJobStatus.failed
    job.error_message = "服务重启导致一键成书任务中断，请重新启动一键成书"
    db.commit()


def _job_to_out(job: BookJob, db: Session) -> BookJobOut:
    detail = build_job_detail(db, job)
    return BookJobOut(
        id=str(job.id),
        book_id=str(job.book_id),
        status=job.status.value,
        current_step=job.current_step.value if job.current_step else None,
        progress_pct=job.progress_pct,
        error_message=job.error_message,
        detail=BookJobDetailOut(**detail),
    )


@router.post("/auto-generate", response_model=BookJobOut, status_code=status.HTTP_201_CREATED)
def start_auto_generate(
    body: AutoGenerateIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "请先创建书稿并确认项目输入、输入理解和写作方案后再启动一键成书",
    )


@router.get("/{book_id}", response_model=BookJobOut)
def get_book_job(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    job = (
        db.query(BookJob)
        .filter(BookJob.book_id == book_id)
        .order_by(BookJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    _reconcile_job_worker(db, job)
    db.refresh(job)
    return _job_to_out(job, db)


@router.post("/{book_id}/start", response_model=BookJobOut, status_code=status.HTTP_201_CREATED)
def start_auto_generate_for_book(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """对已有书稿启动一键生成（设定页保存后调用）。"""
    book = book_service.get_book_or_404(book_id, user, db)
    from app.services.writing.writing_context_builder import WritingContextBuilder

    if getattr(book, "creation_origin", None) and not WritingContextBuilder(db).auto_progress_allowed(book.id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "请先完成项目启动或确认创作意图后再启动一键成书",
        )
    existing = (
        db.query(BookJob)
        .filter(BookJob.book_id == book_id, BookJob.status.in_((BookJobStatus.pending, BookJobStatus.running)))
        .first()
    )
    if existing:
        _reconcile_job_worker(db, existing)
        db.refresh(existing)
        if existing.status in (BookJobStatus.pending, BookJobStatus.running):
            return _job_to_out(existing, db)
    job = BookJob(book_id=book.id, user_id=user.id, status=BookJobStatus.pending, progress_pct=0)
    db.add(job)
    book.status = BookStatus.auto_generating
    db.commit()
    db.refresh(job)
    background_tasks.add_task(dispatch_book_job, job.id)
    return _job_to_out(job, db)
