"""Sync WritingBasis ↔ Book fields and WritingRequirement rows.

Canonical 书稿设定 = Book core fields + WritingBasis extended narrative fields.
Live sync keeps SetupView / 项目要点 / outline inputs aligned during assistant turns.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.material import MaterialTerm, WritingRequirement
from app.models.writing_basis import WritingBasis

_BASIS_REQ_CATEGORIES = (
    "intake_must_keep",
    "intake_must_avoid",
    "intake_material_policy",
    "intake_intent_effect",
    "basis_must_keep",
    "basis_must_avoid",
    "basis_material_policy",
    "basis_reader_outcome",
    "basis_book_promise",
    "basis_scope",
    "basis_depth",
    "basis_voice",
)


def deactivate_intake_material(db: Session, book_id) -> None:
    db.query(WritingRequirement).filter(
        WritingRequirement.book_id == book_id,
        WritingRequirement.category.in_(_BASIS_REQ_CATEGORIES),
    ).update({"active": False})
    db.query(MaterialTerm).filter(
        MaterialTerm.book_id == book_id,
        MaterialTerm.term_type == "intake",
    ).update({"active": False})


def sync_book_fields_from_basis(book: Book, basis: WritingBasis) -> None:
    """Map WritingBasis → Book core fields (in-place, no flush)."""
    if basis.target_readers:
        book.target_audience = str(basis.target_readers)[:500]
    # topic_brief: prefer direction; append reader_outcome cue if brief empty of it
    if basis.direction:
        book.topic_brief = str(basis.direction)[:20_000]
    elif basis.book_promise and not (book.topic_brief or "").strip():
        book.topic_brief = str(basis.book_promise)[:20_000]


def sync_requirements_from_basis(db: Session, book: Book, basis: WritingBasis) -> None:
    deactivate_intake_material(db, book.id)
    sync_book_fields_from_basis(book, basis)

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

    for category, value in (
        ("basis_reader_outcome", basis.reader_outcome),
        ("basis_book_promise", basis.book_promise),
        ("basis_scope", basis.scope),
        ("basis_depth", basis.depth),
        ("basis_voice", basis.voice),
    ):
        if value:
            _add_req(str(value), category, "should")

    for label, value in (
        ("book_goal", basis.direction),
        ("target_readers", basis.target_readers),
        ("scope", basis.scope),
        ("depth", basis.depth),
        ("reader_outcome", basis.reader_outcome),
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
