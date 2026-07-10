"""Aggregate chapter review scores into writing quality summary."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_review import ChapterReview, ChapterReviewIssue
from app.models.review_stage import ReviewStageStatus


class WritingQualityAggregator:
    def __init__(self, db: Session):
        self.db = db

    def aggregate(self, book_id: UUID) -> dict:
        chapters = self.db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.index).all()
        total = len([c for c in chapters if c.index > 0])
        chapter_ids = {c.id: c.index for c in chapters}
        reviews = (
            self.db.query(ChapterReview)
            .filter(ChapterReview.manuscript_id == book_id)
            .order_by(ChapterReview.created_at.desc())
            .all()
        )
        by_chapter: dict[int, ChapterReview] = {}
        for r in reviews:
            ch_index = chapter_ids.get(r.chapter_id)
            if ch_index is not None and ch_index not in by_chapter:
                by_chapter[ch_index] = r
        reviewed = len(by_chapter)
        scores = [float(r.total_score) for r in by_chapter.values() if r.total_score is not None]
        avg = sum(scores) / len(scores) if scores else None
        issue_counts = {"high": 0, "medium": 0, "low": 0}
        dimension_totals: dict[str, list[float]] = {}
        for r in by_chapter.values():
            issues = self.db.query(ChapterReviewIssue).filter(ChapterReviewIssue.review_id == r.id).all()
            for iss in issues:
                sev = str(getattr(iss, "severity", "medium") or "medium").lower()
                if sev in issue_counts:
                    issue_counts[sev] += 1
                dim = str(getattr(iss, "dimension", "") or "general")
                score = getattr(iss, "score", None)
                if score is not None:
                    dimension_totals.setdefault(dim, []).append(float(score))
        dimension_averages = {k: sum(v) / len(v) for k, v in dimension_totals.items() if v}
        return {
            "status": ReviewStageStatus.completed.value if reviewed else ReviewStageStatus.not_started.value,
            "reviewed_chapters": reviewed,
            "total_chapters": total,
            "average_score": avg,
            "issue_counts_by_severity": issue_counts,
            "issueCountsBySeverity": issue_counts,
            "dimensionAverages": dimension_averages,
            "issueCountsBySeverity_legacy": issue_counts,
        }
