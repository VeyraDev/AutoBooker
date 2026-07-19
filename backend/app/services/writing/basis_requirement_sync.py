"""Sync WritingRequirement and book fields from confirmed WritingBasis."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.material import MaterialTerm, WritingRequirement
from app.models.writing_basis import WritingBasis


def deactivate_intake_material(db: Session, book_id) -> None:
    db.query(WritingRequirement).filter(
        WritingRequirement.book_id == book_id,
        WritingRequirement.category.in_(
            (
                "intake_must_keep",
                "intake_must_avoid",
                "intake_material_policy",
                "intake_intent_effect",
                "basis_must_keep",
                "basis_must_avoid",
                "basis_material_policy",
            )
        ),
    ).update({"active": False})
    db.query(MaterialTerm).filter(
        MaterialTerm.book_id == book_id,
        MaterialTerm.term_type == "intake",
    ).update({"active": False})


def sync_requirements_from_basis(db: Session, book: Book, basis: WritingBasis) -> None:
    deactivate_intake_material(db, book.id)

    if basis.target_readers:
        book.target_audience = str(basis.target_readers)[:500]
    if basis.direction:
        book.topic_brief = str(basis.direction)[:20000]

    def _add_req(content: str, category: str, strength: str = "must") -> None:
        if not str(content).strip():
            return
        db.add(
            WritingRequirement(
                book_id=book.id,
                source_file_id=None,
                content=str(content).strip()[:2000],
                category=category,
                strength=strength,
                scope="book",
                active=True,
            )
        )

    for item in basis.must_keep or []:
        _add_req(str(item), "basis_must_keep", "must")
    for item in basis.must_avoid or []:
        _add_req(str(item), "basis_must_avoid", "must")
    for item in basis.material_policy or []:
        _add_req(str(item), "basis_material_policy", "should")
    for item in basis.outline_policy or []:
        _add_req(str(item), "basis_material_policy", "should")

    for label, value in (
        ("book_goal", basis.direction),
        ("target_readers", basis.target_readers),
        ("scope", basis.scope),
        ("depth", basis.depth),
    ):
        if value:
            db.add(
                MaterialTerm(
                    book_id=book.id,
                    source_file_id=None,
                    term=str(value)[:300],
                    term_type="intake",
                    active=True,
                )
            )

    db.flush()
