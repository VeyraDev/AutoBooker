"""Review stage must consume confirmed intake and writing-plan context."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.review_stage.input_alignment_reviewer import InputAlignmentReviewer
from app.services.review_stage.publication_standard_review import PublicationStandardReview


def _chapter(index: int, text: str):
    return SimpleNamespace(id=uuid4(), index=index, title=f"Chapter {index}", content={"text": text})


def test_input_alignment_flags_confirmed_avoid_rule_in_manuscript():
    findings = InputAlignmentReviewer().run(
        [_chapter(1, "This chapter contains empty hype and little substance.")],
        {"must_avoid": ["empty hype"]},
    )

    assert findings
    assert findings[0]["category"] == "input_alignment"
    assert findings[0]["severity"] == "medium"
    assert "empty hype" in findings[0]["detail"]


def test_input_alignment_flags_missing_confirmed_keep_rule():
    findings = InputAlignmentReviewer().run(
        [_chapter(1, "This chapter discusses product discovery.")],
        {"must_keep": ["AI governance checklist"]},
    )

    assert findings
    assert findings[0]["category"] == "input_alignment"
    assert findings[0]["severity"] == "low"
    assert "AI governance checklist" in findings[0]["detail"]


def test_publication_standard_summary_records_input_effects(monkeypatch):
    review = PublicationStandardReview(SimpleNamespace())
    monkeypatch.setattr(review.structure, "run", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(review.content, "run", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(review.copy, "run", lambda *_args, **_kwargs: [])

    summary, findings = review.run(
        SimpleNamespace(id=uuid4(), title="AI Book"),
        [_chapter(1, "Generated text.")],
        context_snapshot={
            "understanding_id": str(uuid4()),
            "writing_plan_id": str(uuid4()),
            "intent_effects": [
                {
                    "input_ref": "user onboarding notes",
                    "writing_effect": "use recurring chapter examples",
                    "applies_to": ["chapters", "review"],
                }
            ],
        },
    )

    assert findings == []
    assert summary["input_alignment_checked"] is True
    assert summary["input_effect_count"] == 1
    assert summary["input_alignment_suggestion_count"] == 0
