"""Book review stage: dual-track non-blocking review."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.review_stage import (
    BookReviewFinding,
    BookReviewStageRun,
    ReviewFindingStatus,
    ReviewStageStatus,
    ReviewTrack,
)
from app.services.review_stage.publication_standard_review import PublicationStandardReview
from app.services.review_stage.review_finding_service import ReviewFindingService
from app.services.review_stage.writing_quality_aggregator import WritingQualityAggregator
from app.services.writing.writing_context_builder import WritingContextBuilder


class ReviewStageService:
    def __init__(self, db: Session):
        self.db = db
        self.wq = WritingQualityAggregator(db)
        self.pub = PublicationStandardReview(db)
        self.findings = ReviewFindingService(db)

    def run(self, book: Book) -> BookReviewStageRun:
        from app.services.citation_service import is_bibliography_chapter

        run = BookReviewStageRun(
            book_id=book.id,
            status=ReviewStageStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.flush()

        chapters = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book.id)
            .order_by(Chapter.index)
            .all()
        )
        chapters = [c for c in chapters if not is_bibliography_chapter(c)]

        wcb = WritingContextBuilder(self.db)
        snap = wcb.build_for_review(book.id)
        context_ref = {"context_hash": wcb.context_hash(snap), "understanding_id": snap.get("understanding_id")}

        wq_summary = self.wq.aggregate(book.id)
        pub_summary, pub_findings_data = self.pub.run(
            book,
            chapters,
            context_excerpt=wcb.to_prompt_block(snap)[:2000],
            context_snapshot=snap,
        )
        self.findings.persist_batch(
            run_id=run.id,
            book_id=book.id,
            track=ReviewTrack.publication_standard,
            items=pub_findings_data,
            source_ref=context_ref,
            context_snapshot=snap,
        )

        from app.services.review.format_column_reviewer import run_format_column_review

        format_findings = run_format_column_review(chapters, snap)
        if format_findings:
            self.findings.persist_batch(
                run_id=run.id,
                book_id=book.id,
                track=ReviewTrack.publication_standard,
                items=format_findings,
                source_ref=context_ref,
                context_snapshot=snap,
            )

        run.writing_quality_status = ReviewStageStatus(wq_summary["status"])
        run.publication_standard_status = ReviewStageStatus(pub_summary["status"])
        run.summary_json = {"writing_quality": wq_summary, "publication_standard": pub_summary}
        run.status = ReviewStageStatus.completed
        run.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(run)
        return run

    def summary(self, book_id: UUID) -> dict | None:
        run = (
            self.db.query(BookReviewStageRun)
            .filter(BookReviewStageRun.book_id == book_id)
            .order_by(BookReviewStageRun.created_at.desc())
            .first()
        )
        if not run:
            return {
                "book_id": str(book_id),
                "status": ReviewStageStatus.not_started.value,
                "tracks": {
                    "writing_quality": {"status": ReviewStageStatus.not_started.value},
                    "publication_standard": {"status": ReviewStageStatus.not_started.value},
                },
            }
        sj = run.summary_json if isinstance(run.summary_json, dict) else {}
        open_count = (
            self.db.query(func.count(BookReviewFinding.id))
            .filter(BookReviewFinding.run_id == run.id, BookReviewFinding.status == ReviewFindingStatus.open)
            .scalar()
        )
        return {
            "book_id": str(book_id),
            "status": run.status.value,
            "tracks": {
                "writing_quality": sj.get("writing_quality") or {"status": run.writing_quality_status.value if run.writing_quality_status else "not_started"},
                "publication_standard": sj.get("publication_standard") or {"status": run.publication_standard_status.value if run.publication_standard_status else "not_started"},
            },
            "suggestion_count": int(open_count or 0),
            "updated_at": run.finished_at.isoformat() if run.finished_at else None,
        }
