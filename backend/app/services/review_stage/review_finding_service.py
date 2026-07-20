"""Review findings CRUD helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.review_stage import BookReviewFinding, ReviewFindingStatus, ReviewTrack
from app.services.review.review_finding_validator import enrich_finding_metadata, validate_finding
from app.services.review.review_rule_library import match_basis_refs
from app.services.review_anchor import locate_issue_anchor
from app.services.tiptap_convert import chapter_content_to_markdown


_FINDING_META_KEYS = (
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
    "quote",
    "paragraph_id",
    "paragraph_index",
    "char_start",
    "char_end",
    "detector",
    "dimension",
    "issue_type",
    "confidence",
)

_QUALITY_EVIDENCE_KEYS = (
    "title_benchmark",
    "evidence",
    "source_refs",
    "evidence_gap",
)


def build_finding_source_ref(
    finding: dict,
    *,
    source_ref: dict | None = None,
    chapter_md: str | None = None,
) -> dict:
    """Preserve evidence and resolve a stable manuscript anchor before persistence."""
    ref = dict(source_ref or {})
    for key in _FINDING_META_KEYS:
        if finding.get(key) is not None:
            ref[key] = finding.get(key)

    quality_evidence = finding.get("quality_evidence")
    if isinstance(quality_evidence, dict):
        for key in _QUALITY_EVIDENCE_KEYS:
            if quality_evidence.get(key) is not None:
                ref[key] = quality_evidence.get(key)

    if not chapter_md:
        return ref

    anchor_query = str(finding.get("quote") or finding.get("detail") or "").strip()
    if not anchor_query:
        ref["locatable"] = False
        return ref
    located = locate_issue_anchor(
        chapter_md,
        quote=anchor_query,
        paragraph_id=finding.get("paragraph_id"),
        paragraph_index=finding.get("paragraph_index"),
        char_start=finding.get("char_start"),
        char_end=finding.get("char_end"),
    )
    locatable = located.char_start is not None and located.confidence >= 0.5
    ref.update(
        {
            "locatable": locatable,
            "locator_strategy": located.strategy,
            "locator_confidence": located.confidence,
        }
    )
    if locatable:
        ref.update(
            {
                "quote": str(finding.get("quote") or located.quote or anchor_query),
                "paragraph_id": located.paragraph_id,
                "paragraph_index": located.paragraph_index,
                "char_start": located.char_start,
                "char_end": located.char_end,
                "anchor_hash": located.anchor_hash,
            }
        )
    return ref


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
        chapter_markdown = {
            chapter.index: chapter_content_to_markdown(
                chapter.content if isinstance(chapter.content, dict) else None
            )
            for chapter in self.db.query(Chapter).filter(Chapter.book_id == book_id).all()
        }
        for fd in items:
            chapter_index = fd.get("chapter_index")
            chapter_md = chapter_markdown.get(chapter_index)
            enriched = enrich_finding_metadata(fd, context_snapshot, chapter_md=chapter_md)
            validated = validate_finding(
                enriched,
                book_level=chapter_index is None,
                chapter_md=chapter_md,
            )
            if not validated:
                continue
            basis = match_basis_refs(validated, context_snapshot)
            ref = build_finding_source_ref(validated, source_ref=source_ref, chapter_md=chapter_md)
            if basis:
                ref["basis_refs"] = basis
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
