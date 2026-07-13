"""WritingBasisService unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.writing_basis import WritingBasis, WritingBasisStatus
from app.services.writing.writing_basis_service import WritingBasisService


class _FilterQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._book_id = None
        self._status = None

    def filter(self, *args, **_kwargs):
        for arg in args:
            if hasattr(arg, "left") and hasattr(arg, "right"):
                key = arg.left.key
                val = arg.right.value if hasattr(arg.right, "value") else arg.right
                if key == "book_id":
                    self._book_id = val
                elif key == "status":
                    self._status = val
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        rows = self._matching()
        return rows[0] if rows else None

    def all(self):
        return self._matching()

    def count(self):
        return len(self._rows)

    def _matching(self):
        result = self._rows
        if self._book_id is not None:
            result = [r for r in result if getattr(r, "book_id", None) == self._book_id]
        if self._status is not None:
            result = [r for r in result if getattr(r, "status", None) == self._status]
        return result


class _Db:
    def __init__(self, bases=None):
        self.bases = list(bases or [])
        self.added: list[WritingBasis] = []

    def query(self, model):
        if model is WritingBasis:
            return _FilterQuery(self.bases + self.added)
        return _FilterQuery([])

    def add(self, row):
        self.added.append(row)

    def flush(self):
        return None


def _book():
    return SimpleNamespace(id=uuid4())


def _intake():
    return SimpleNamespace(id=uuid4(), negative_constraints_text="Avoid hype.")


def _understanding():
    return SimpleNamespace(
        id=uuid4(),
        summary_json={
            "book_goal": "Practical AI adoption",
            "intent_json": {
                "book_promise": "Help teams adopt AI safely.",
                "reader_outcome": "Plan safer workflows.",
            },
        },
        preserve_rules=["Keep onboarding examples"],
        avoid_rules=["No empty hype"],
        unclear_questions=["Need case studies?"],
    )


def _plan():
    return SimpleNamespace(
        id=uuid4(),
        plan_json={
            "direction": "AI adoption playbook",
            "audience": "Product teams",
            "content_boundary": "Hands-on workflows only",
            "depth": "Intermediate",
            "voice": "Direct and practical",
            "material_policy": ["Use onboarding notes as examples"],
            "must_keep": ["Real team decisions"],
            "must_avoid": ["Trend reports"],
        },
    )


def test_materialize_maps_plan_and_understanding_fields():
    svc = WritingBasisService(_Db())  # type: ignore[arg-type]
    fields = svc.materialize_fields(
        understanding=_understanding(),
        plan=_plan(),
        intake=_intake(),
    )
    assert fields["direction"] == "AI adoption playbook"
    assert fields["book_promise"] == "Help teams adopt AI safely."
    assert fields["target_readers"] == "Product teams"
    assert "Real team decisions" in fields["must_keep"]
    assert "Keep onboarding examples" in fields["must_keep"]
    assert "Trend reports" in fields["must_avoid"]
    assert "No empty hype" in fields["must_avoid"]
    assert "Avoid hype." in fields["must_avoid"]


def test_confirm_supersedes_previous_confirmed():
    book_id = uuid4()
    old = SimpleNamespace(
        id=uuid4(),
        book_id=book_id,
        status=WritingBasisStatus.confirmed,
        direction="Old",
        book_promise=None,
        version=1,
    )
    draft = WritingBasis(
        id=uuid4(),
        book_id=book_id,
        version=2,
        status=WritingBasisStatus.draft,
        direction="New direction",
        book_promise=None,
    )
    db = _Db(bases=[old])
    svc = WritingBasisService(db)  # type: ignore[arg-type]
    svc.confirm(draft)
    assert old.status == WritingBasisStatus.superseded
    assert draft.status == WritingBasisStatus.confirmed


def test_confirm_rejects_empty_basis():
    basis = WritingBasis(
        id=uuid4(),
        book_id=uuid4(),
        version=1,
        status=WritingBasisStatus.draft,
    )
    svc = WritingBasisService(_Db())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="direction or book_promise"):
        svc.confirm(basis)


def test_patch_updates_draft_fields():
    basis = WritingBasis(
        id=uuid4(),
        book_id=uuid4(),
        version=1,
        status=WritingBasisStatus.draft,
        direction="Before",
        must_avoid=[],
    )
    svc = WritingBasisService(_Db())  # type: ignore[arg-type]
    svc.patch(basis, {"direction": "After", "must_avoid": ["No jargon"]})
    assert basis.direction == "After"
    assert basis.must_avoid == ["No jargon"]
