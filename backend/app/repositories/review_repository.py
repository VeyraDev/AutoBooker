"""审校报告、issue 与应用记录仓储。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_review import ChapterReview, ChapterReviewIssue, ReviewApplication
from app.services.review_scoring import aggregate_review, issue_fingerprint, weights_snapshot


def create_review(
    db: Session,
    *,
    chapter: Chapter,
    manuscript_id: UUID,
    snapshot_hash: str,
    markdown_snapshot: str,
    dimensions: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    total_score: int,
    status: str,
    model_name: str,
    prompt_version: str = "review_agent_v2",
    score_schema_version: str = "review_v2",
    constitution_hash: str | None = None,
    citation_index_hash: str | None = None,
    figure_index_hash: str | None = None,
) -> ChapterReview:
    review = ChapterReview(
        chapter_id=chapter.id,
        manuscript_id=manuscript_id,
        snapshot_hash=snapshot_hash,
        markdown_snapshot=markdown_snapshot,
        total_score=total_score,
        dimensions=dimensions,
        weights=weights_snapshot(),
        score_schema_version=score_schema_version,
        prompt_version=prompt_version,
        model_name=model_name,
        constitution_hash=constitution_hash,
        citation_index_hash=citation_index_hash,
        figure_index_hash=figure_index_hash,
        status=status,
    )
    db.add(review)
    db.flush()
    for raw in issues:
        fp = raw.get("issue_fingerprint") or issue_fingerprint(raw)
        db.add(
            ChapterReviewIssue(
                review_id=review.id,
                chapter_id=chapter.id,
                snapshot_hash=snapshot_hash,
                dimension=raw["dimension"],
                issue_type=raw["issue_type"],
                severity=raw["severity"],
                penalty=int(raw.get("penalty") or 0),
                status=raw.get("status") or "open",
                title=raw.get("title") or "",
                explanation=raw.get("explanation") or "",
                quote=raw.get("quote") or "",
                action=raw.get("action") or "revise",
                replacement_text=raw.get("replacement_text") or "",
                paragraph_id=raw.get("paragraph_id"),
                paragraph_index=raw.get("paragraph_index"),
                char_start=raw.get("char_start"),
                char_end=raw.get("char_end"),
                anchor_hash=raw.get("anchor_hash"),
                issue_fingerprint=fp,
                detector=raw.get("detector") or "review_agent",
                confidence=raw.get("confidence") or 0.7,
            )
        )
    db.commit()
    db.refresh(review)
    return review


def latest_review(db: Session, chapter_id: UUID) -> ChapterReview | None:
    return (
        db.query(ChapterReview)
        .filter(ChapterReview.chapter_id == chapter_id)
        .order_by(ChapterReview.created_at.desc())
        .first()
    )


def review_history(db: Session, chapter_id: UUID, *, limit: int = 20, offset: int = 0) -> list[ChapterReview]:
    return (
        db.query(ChapterReview)
        .filter(ChapterReview.chapter_id == chapter_id)
        .order_by(ChapterReview.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_review(db: Session, review_id: UUID) -> ChapterReview | None:
    return db.get(ChapterReview, review_id)


def get_issue(db: Session, issue_id: UUID) -> ChapterReviewIssue | None:
    return db.get(ChapterReviewIssue, issue_id)


def list_issues(
    db: Session,
    review_id: UUID,
    *,
    dimension: str | None = None,
    severity: str | None = None,
    status: str | None = None,
) -> list[ChapterReviewIssue]:
    q = db.query(ChapterReviewIssue).filter(ChapterReviewIssue.review_id == review_id)
    if dimension:
        q = q.filter(ChapterReviewIssue.dimension == dimension)
    if severity:
        q = q.filter(ChapterReviewIssue.severity == severity)
    if status:
        q = q.filter(ChapterReviewIssue.status == status)
    return q.order_by(ChapterReviewIssue.created_at.asc()).all()


def set_issue_status(db: Session, issue: ChapterReviewIssue, status: str) -> ChapterReviewIssue:
    now = datetime.now(timezone.utc)
    issue.status = status
    if status in {"applied", "resolved"}:
        issue.applied_at = issue.applied_at or now
    if status == "resolved":
        issue.resolved_at = now
    if status == "dismissed":
        issue.dismissed_at = now
    db.commit()
    db.refresh(issue)
    _recompute_review_scores(db, issue.review_id)
    return issue


def create_application(
    db: Session,
    *,
    issue: ChapterReviewIssue | None,
    review: ChapterReview | None,
    chapter_id: UUID,
    before_hash: str,
    after_hash: str,
    apply_type: str,
    locator_strategy: str,
    locator_confidence: float,
    diff: dict[str, Any],
    affected_dimensions: list[str],
    score_before: dict[str, Any] | None = None,
    score_after: dict[str, Any] | None = None,
    warning: dict[str, Any] | None = None,
) -> ReviewApplication:
    app = ReviewApplication(
        issue_id=issue.id if issue else None,
        review_id=review.id if review else None,
        chapter_id=chapter_id,
        before_hash=before_hash,
        after_hash=after_hash,
        apply_type=apply_type,
        locator_strategy=locator_strategy,
        locator_confidence=locator_confidence,
        diff=diff,
        affected_dimensions=affected_dimensions,
        score_before=score_before,
        score_after=score_after,
        warning=warning,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def latest_application(db: Session, chapter_id: UUID) -> ReviewApplication | None:
    return (
        db.query(ReviewApplication)
        .filter(ReviewApplication.chapter_id == chapter_id)
        .order_by(ReviewApplication.created_at.desc())
        .first()
    )


def _recompute_review_scores(db: Session, review_id: UUID) -> None:
    review = db.get(ChapterReview, review_id)
    if not review:
        return
    issues = [_issue_to_dict(i) for i in review.issues]
    detector_dims = {str(d.get("key") or d.get("dimension")): d for d in (review.dimensions or [])}
    dimensions, total, status = aggregate_review(detector_dims, issues)
    review.dimensions = dimensions
    review.total_score = total
    review.status = status
    db.commit()


def _issue_to_dict(issue: ChapterReviewIssue) -> dict[str, Any]:
    return {
        "dimension": issue.dimension,
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "penalty": issue.penalty,
        "status": issue.status,
        "title": issue.title,
        "explanation": issue.explanation,
        "quote": issue.quote,
        "action": issue.action,
        "replacement_text": issue.replacement_text,
        "paragraph_id": issue.paragraph_id,
        "paragraph_index": issue.paragraph_index,
        "char_start": issue.char_start,
        "char_end": issue.char_end,
        "anchor_hash": issue.anchor_hash,
        "issue_fingerprint": issue.issue_fingerprint,
        "detector": issue.detector,
        "confidence": float(issue.confidence or 0),
    }
