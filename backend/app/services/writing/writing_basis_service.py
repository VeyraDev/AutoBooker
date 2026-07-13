"""Writing basis service — materialize, patch, confirm."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.intake import InputUnderstanding, ProjectIntake, WritingPlan
from app.models.writing_basis import WritingBasis, WritingBasisStatus


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unique_strings(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


class WritingBasisService:
    def __init__(self, db: Session):
        self.db = db

    def get_confirmed(self, book_id: UUID) -> WritingBasis | None:
        return (
            self.db.query(WritingBasis)
            .filter(WritingBasis.book_id == book_id, WritingBasis.status == WritingBasisStatus.confirmed)
            .order_by(WritingBasis.version.desc())
            .first()
        )

    def get_draft(self, book_id: UUID) -> WritingBasis | None:
        return (
            self.db.query(WritingBasis)
            .filter(WritingBasis.book_id == book_id, WritingBasis.status == WritingBasisStatus.draft)
            .order_by(WritingBasis.version.desc())
            .first()
        )

    def get_active(self, book_id: UUID) -> WritingBasis | None:
        confirmed = self.get_confirmed(book_id)
        if confirmed:
            return confirmed
        draft = self.get_draft(book_id)
        if draft:
            return draft
        return self.materialize_from_confirmed_intake(book_id)

    def materialize_from_confirmed_intake(self, book_id: UUID) -> WritingBasis | None:
        """Lazy backfill WritingBasis from legacy confirmed intake artifacts."""
        from app.models.intake import (
            InputUnderstanding,
            IntakeStatus,
            ProjectIntake,
            UnderstandingStatus,
            WritingPlan,
            WritingPlanStatus,
        )

        if self.get_confirmed(book_id) or self.get_draft(book_id):
            return self.get_active(book_id)

        intake = (
            self.db.query(ProjectIntake)
            .filter(ProjectIntake.book_id == book_id, ProjectIntake.status == IntakeStatus.confirmed)
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if not intake:
            return None

        understanding = None
        if intake.confirmed_understanding_id:
            understanding = (
                self.db.query(InputUnderstanding)
                .filter(InputUnderstanding.id == intake.confirmed_understanding_id)
                .first()
            )
        if not understanding:
            understanding = (
                self.db.query(InputUnderstanding)
                .filter(
                    InputUnderstanding.intake_id == intake.id,
                    InputUnderstanding.status == UnderstandingStatus.confirmed,
                )
                .order_by(InputUnderstanding.version.desc())
                .first()
            )

        plan = None
        if intake.confirmed_writing_plan_id:
            plan = self.db.query(WritingPlan).filter(WritingPlan.id == intake.confirmed_writing_plan_id).first()
        if not plan:
            plan = (
                self.db.query(WritingPlan)
                .filter(
                    WritingPlan.intake_id == intake.id,
                    WritingPlan.status == WritingPlanStatus.confirmed,
                )
                .order_by(WritingPlan.version.desc())
                .first()
            )

        if not understanding or not plan:
            return None

        basis = self.materialize_and_confirm(
            self.db.query(Book).filter(Book.id == book_id).first(),
            intake,
            understanding,
            plan,
        )
        return basis

    def _next_version(self, book_id: UUID) -> int:
        count = self.db.query(WritingBasis).filter(WritingBasis.book_id == book_id).count()
        return count + 1

    def _supersede_confirmed(self, book_id: UUID) -> None:
        rows = (
            self.db.query(WritingBasis)
            .filter(WritingBasis.book_id == book_id, WritingBasis.status == WritingBasisStatus.confirmed)
            .all()
        )
        for row in rows:
            row.status = WritingBasisStatus.superseded

    def materialize_fields(
        self,
        *,
        understanding: InputUnderstanding,
        plan: WritingPlan,
        intake: ProjectIntake | None = None,
    ) -> dict[str, Any]:
        plan_json = _as_dict(plan.plan_json)
        summary_json = _as_dict(understanding.summary_json)
        intent_json = _as_dict(summary_json.get("intent_json"))

        must_keep = _unique_strings(
            list(plan_json.get("must_keep") or []) + list(understanding.preserve_rules or [])
        )
        must_avoid = _unique_strings(
            list(plan_json.get("must_avoid") or [])
            + list(understanding.avoid_rules or [])
            + ([intake.negative_constraints_text] if intake and intake.negative_constraints_text else [])
        )

        return {
            "direction": _first_text(plan_json.get("direction"), summary_json.get("book_goal")),
            "book_promise": _first_text(intent_json.get("book_promise")),
            "target_readers": _first_text(plan_json.get("audience"), summary_json.get("target_readers")),
            "reader_outcome": _first_text(intent_json.get("reader_outcome")),
            "scope": _first_text(plan_json.get("content_boundary"), summary_json.get("scope")),
            "depth": _first_text(plan_json.get("depth"), summary_json.get("depth")),
            "voice": _first_text(plan_json.get("voice")),
            "material_policy": _unique_strings(list(plan_json.get("material_policy") or [])),
            "outline_policy": [],
            "citation_policy": [],
            "figure_policy": [],
            "must_keep": must_keep,
            "must_avoid": must_avoid,
            "open_questions": _as_list(understanding.unclear_questions),
            "source_understanding_id": understanding.id,
            "source_plan_id": plan.id,
        }

    def create_empty_draft(self, book: Book) -> WritingBasis:
        basis = WritingBasis(
            book_id=book.id,
            version=self._next_version(book.id),
            status=WritingBasisStatus.draft,
            material_policy=[],
            outline_policy=[],
            citation_policy=[],
            figure_policy=[],
            must_keep=[],
            must_avoid=[],
            open_questions=[],
        )
        self.db.add(basis)
        self.db.flush()
        return basis

    def get_draft_or_create(self, book: Book) -> WritingBasis:
        draft = self.get_draft(book.id)
        if draft:
            return draft
        return self.create_empty_draft(book)

    def create_draft_from_intake(
        self,
        book: Book,
        understanding: InputUnderstanding,
        plan: WritingPlan,
        *,
        intake: ProjectIntake | None = None,
    ) -> WritingBasis:
        fields = self.materialize_fields(understanding=understanding, plan=plan, intake=intake)
        basis = WritingBasis(
            book_id=book.id,
            version=self._next_version(book.id),
            status=WritingBasisStatus.draft,
            **fields,
        )
        self.db.add(basis)
        self.db.flush()
        return basis

    def patch(self, basis: WritingBasis, patch: dict[str, Any]) -> WritingBasis:
        if basis.status != WritingBasisStatus.draft:
            raise ValueError("Only draft writing basis can be patched")
        list_fields = {
            "material_policy",
            "outline_policy",
            "citation_policy",
            "figure_policy",
            "must_keep",
            "must_avoid",
            "open_questions",
        }
        text_fields = {
            "direction",
            "book_promise",
            "target_readers",
            "reader_outcome",
            "scope",
            "depth",
            "voice",
        }
        for key, value in patch.items():
            if key in text_fields and value is not None:
                setattr(basis, key, str(value).strip() or None)
            elif key in list_fields and value is not None:
                setattr(basis, key, _as_list(value))
        self.db.flush()
        return basis

    def _validate_confirmable(self, basis: WritingBasis) -> None:
        if not _first_text(basis.direction, basis.book_promise):
            raise ValueError("Writing basis must have direction or book_promise before confirm")

    def confirm(self, basis: WritingBasis, *, intake: ProjectIntake | None = None) -> WritingBasis:
        self._validate_confirmable(basis)
        self._supersede_confirmed(basis.book_id)
        basis.status = WritingBasisStatus.confirmed
        if intake is not None:
            intake.confirmed_writing_basis_id = basis.id
        self.db.flush()
        return basis

    def finalize_confirm(
        self,
        book: Book,
        basis: WritingBasis,
        *,
        intake: ProjectIntake | None = None,
    ) -> WritingBasis:
        from app.models.intake import IntakeStatus
        from app.services.writing.basis_requirement_sync import sync_requirements_from_basis
        from app.services.writing.writing_context_builder import WritingContextBuilder

        basis = self.confirm(basis, intake=intake)
        if intake is not None:
            intake.status = IntakeStatus.confirmed
        sync_requirements_from_basis(self.db, book, basis)
        WritingContextBuilder(self.db).persist_snapshot(
            book.id,
            "writing_basis_confirm",
            WritingContextBuilder(self.db).build_snapshot(book.id),
        )
        self.db.flush()
        return basis

    def materialize_and_confirm(
        self,
        book: Book,
        intake: ProjectIntake,
        understanding: InputUnderstanding,
        plan: WritingPlan,
    ) -> WritingBasis:
        fields = self.materialize_fields(understanding=understanding, plan=plan, intake=intake)
        basis = WritingBasis(
            book_id=book.id,
            version=self._next_version(book.id),
            status=WritingBasisStatus.confirmed,
            **fields,
        )
        self._validate_confirmable(basis)
        self._supersede_confirmed(book.id)
        self.db.add(basis)
        intake.confirmed_writing_basis_id = basis.id
        self.db.flush()
        return basis

    def to_dict(self, basis: WritingBasis) -> dict[str, Any]:
        return {
            "id": str(basis.id),
            "book_id": str(basis.book_id),
            "version": basis.version,
            "status": basis.status.value,
            "direction": basis.direction,
            "book_promise": basis.book_promise,
            "target_readers": basis.target_readers,
            "reader_outcome": basis.reader_outcome,
            "scope": basis.scope,
            "depth": basis.depth,
            "voice": basis.voice,
            "material_policy": list(basis.material_policy or []),
            "outline_policy": list(basis.outline_policy or []),
            "citation_policy": list(basis.citation_policy or []),
            "figure_policy": list(basis.figure_policy or []),
            "must_keep": list(basis.must_keep or []),
            "must_avoid": list(basis.must_avoid or []),
            "open_questions": list(basis.open_questions or []),
            "source_understanding_id": str(basis.source_understanding_id) if basis.source_understanding_id else None,
            "source_plan_id": str(basis.source_plan_id) if basis.source_plan_id else None,
        }
