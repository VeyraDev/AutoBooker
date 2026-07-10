"""Orchestrate publication standard review tracks."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.review_stage import ReviewStageStatus
from app.services.review_stage.content_risk_reviewer import ContentRiskReviewer
from app.services.review_stage.copyediting_scanner import CopyeditingScanner
from app.services.review_stage.export_structure_reviewer import ExportStructureReviewer
from app.services.review_stage.input_alignment_reviewer import InputAlignmentReviewer


class PublicationStandardReview:
    def __init__(self, db: Session):
        self.db = db
        self.structure = ExportStructureReviewer(db)
        self.content = ContentRiskReviewer()
        self.copy = CopyeditingScanner()
        self.input_alignment = InputAlignmentReviewer()

    def run(
        self,
        book: Book,
        chapters: list[Chapter],
        *,
        context_excerpt: str = "",
        context_snapshot: dict | None = None,
    ) -> tuple[dict, list[dict]]:
        findings: list[dict] = []
        findings.extend(self.structure.run(book, chapters))
        findings.extend(self.content.run(book, chapters, context_excerpt=context_excerpt))
        findings.extend(self.copy.run(chapters))
        input_alignment_findings = self.input_alignment.run(chapters, context_snapshot)
        findings.extend(input_alignment_findings)
        snap = context_snapshot if isinstance(context_snapshot, dict) else {}
        input_effects = snap.get("intent_effects") or []
        summary = {
            "status": ReviewStageStatus.completed.value,
            "content_risk_count": len([f for f in findings if f["category"] == "content_risk"]),
            "copyright_risk_count": len([f for f in findings if f["category"] == "citation_risk"]),
            "candidate_copyediting_issue_count": len([f for f in findings if f["category"] == "copyediting"]),
            "input_alignment_suggestion_count": len(input_alignment_findings),
            "input_alignment_checked": bool(snap.get("understanding_id") or snap.get("writing_plan_id") or input_effects),
            "input_effect_count": len(input_effects),
            "structure_suggestion_count": len(
                [f for f in findings if f["category"] in ("book_structure", "export_structure")]
            ),
            "export_structure_ready": not any(
                f["category"] == "export_structure" and f["severity"] == "high" for f in findings
            ),
        }
        return summary, findings
