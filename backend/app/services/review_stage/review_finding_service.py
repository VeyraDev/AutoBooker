"""Review findings CRUD helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.review_stage import BookReviewFinding, ReviewFindingStatus, ReviewTrack


class ReviewFindingService:
    def __init__(self, db: Session):
        self.db = db

    def list_for_book(self, book_id: UUID, *, run_id: UUID | None = None) -> list[BookReviewFinding]:
        q = self.db.query(BookReviewFinding).filter(BookReviewFinding.book_id == book_id)
        if run_id:
            q = q.filter(BookReviewFinding.run_id == run_id)
        return q.order_by(BookReviewFinding.created_at.desc()).all()

    def update_status(self, finding_id: UUID, book_id: UUID, status: ReviewFindingStatus) -> BookReviewFinding | None:
        row = (
            self.db.query(BookReviewFinding)
            .filter(BookReviewFinding.id == finding_id, BookReviewFinding.book_id == book_id)
            .first()
        )
        if not row:
            return None
        row.status = status
        self.db.flush()
        return row

    def persist_batch(
        self,
        *,
        run_id: UUID,
        book_id: UUID,
        track: ReviewTrack,
        items: list[dict],
        source_ref: dict | None = None,
    ) -> None:
        for fd in items:
            self.db.add(
                BookReviewFinding(
                    run_id=run_id,
                    book_id=book_id,
                    track=track,
                    category=fd["category"],
                    severity=fd["severity"],
                    title=fd["title"],
                    detail=fd["detail"],
                    suggestion=fd.get("suggestion") or fd["detail"],
                    status=ReviewFindingStatus.open,
                    source_ref_json=source_ref,
                )
            )
