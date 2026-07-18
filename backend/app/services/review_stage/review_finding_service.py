"""Review findings CRUD helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.review_stage import BookReviewFinding, ReviewFindingStatus, ReviewTrack
from app.services.review.review_finding_validator import enrich_finding_metadata, validate_finding
from app.services.review.review_rule_library import match_basis_refs


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
        context_snapshot: dict | None = None,
    ) -> None:
        for fd in items:
            enriched = enrich_finding_metadata(fd, context_snapshot)
            validated = validate_finding(enriched, book_level=True)
            if not validated:
                continue
            basis = match_basis_refs(validated, context_snapshot)
            ref = dict(source_ref or {})
            if basis:
                ref["basis_refs"] = basis
            for key in (
                "task_id",
                "product_dimension",
                "impact_scope",
                "locatable",
                "validation_passed",
                "filter_reason",
                "why_it_matters",
                "verification_status",
                "action_options",
                "fix_capability",
                "prefer_evidence_binding",
                "chapter_index",
            ):
                if validated.get(key) is not None:
                    ref[key] = validated.get(key)
            self.db.add(
                BookReviewFinding(
                    run_id=run_id,
                    book_id=book_id,
                    track=track,
                    category=validated["category"],
                    severity=validated.get("severity") or fd.get("severity") or "medium",
                    title=validated["title"],
                    detail=validated["detail"],
                    suggestion=validated.get("suggestion") or validated["detail"],
                    status=ReviewFindingStatus.open,
                    source_ref_json=ref or None,
                )
            )
