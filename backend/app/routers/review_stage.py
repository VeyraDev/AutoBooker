"""Review stage API (non-blocking)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.book import Book
from app.models.review_stage import BookReviewFinding, ReviewFindingStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.services import book_service
from app.services.review_stage.review_stage_service import ReviewStageService

router = APIRouter(prefix="/books", tags=["review-stage"])


class FindingPatchIn(BaseModel):
    status: ReviewFindingStatus


def _run_review(book_id: UUID) -> None:
    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            ReviewStageService(db).run(book)
    finally:
        db.close()


@router.post("/{book_id}/review-stage/run")
def run_review_stage(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy API — delegates to ReviewAgentService (use review-workspace/run instead)."""
    book = book_service.get_book_or_404(book_id, user, db)
    from app.services.review.review_agent_service import ReviewAgentService

    agent = ReviewAgentService(db)
    task = agent.build_task(book, scope="book")
    result = agent.run_task(book, task, user=user)
    db.commit()
    return {"run_id": result.get("run_id"), "status": result.get("status"), "task_id": result.get("task_id")}


@router.get("/{book_id}/review-stage/summary")
def review_stage_summary(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    return ReviewStageService(db).summary(book_id)


@router.get("/{book_id}/review-stage/findings")
def review_stage_findings(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    from app.models.review_stage import BookReviewStageRun

    run = (
        db.query(BookReviewStageRun)
        .filter(BookReviewStageRun.book_id == book_id)
        .order_by(BookReviewStageRun.created_at.desc())
        .first()
    )
    if not run:
        return {"findings": []}
    rows = db.query(BookReviewFinding).filter(BookReviewFinding.run_id == run.id).all()
    return {
        "findings": [
            {
                "id": str(f.id),
                "track": f.track.value,
                "category": f.category,
                "severity": f.severity,
                "status": f.status.value,
                "title": f.title,
                "detail": f.detail,
                "suggestion": f.suggestion,
            }
            for f in rows
        ]
    }


@router.patch("/{book_id}/review-stage/findings/{finding_id}")
def patch_finding(
    book_id: UUID,
    finding_id: UUID,
    body: FindingPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    f = db.query(BookReviewFinding).filter(BookReviewFinding.id == finding_id, BookReviewFinding.book_id == book_id).first()
    if not f:
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    f.status = body.status
    db.commit()
    return {"id": str(f.id), "status": f.status.value}
