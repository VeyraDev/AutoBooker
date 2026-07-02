"""一键生成书稿 Job API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.constants.style_types import coerce_style
from app.database import get_db
from app.models.book import BookStatus, BookType
from app.models.book_job import BookJob, BookJobStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.book_job import AutoGenerateIn, BookJobDetailOut, BookJobOut
from app.services import book_service
from app.services.auto_book_job import run_auto_book_job
from app.services.auto_book_job_progress import build_job_detail

router = APIRouter(prefix="/book-jobs", tags=["book-jobs"])


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
    bt = body.book_type
    st = coerce_style(bt, body.style_type).value
    book = book_service.create_book(
        user,
        {
            "title": body.title.strip(),
            "book_type": BookType(body.book_type),
            "style_type": st,
            "discipline": body.discipline,
        },
        db,
    )
    job = BookJob(book_id=book.id, user_id=user.id, status=BookJobStatus.pending, progress_pct=0)
    db.add(job)
    book.status = BookStatus.auto_generating
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_auto_book_job, job.id)
    return _job_to_out(job, db)


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
    existing = (
        db.query(BookJob)
        .filter(BookJob.book_id == book_id, BookJob.status.in_((BookJobStatus.pending, BookJobStatus.running)))
        .first()
    )
    if existing:
        return _job_to_out(existing, db)
    job = BookJob(book_id=book.id, user_id=user.id, status=BookJobStatus.pending, progress_pct=0)
    db.add(job)
    book.status = BookStatus.auto_generating
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_auto_book_job, job.id)
    return _job_to_out(job, db)
