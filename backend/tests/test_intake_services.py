"""Intake understanding is LLM-driven and must affect downstream writing."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.book import CreationOrigin
from app.models.intake import InputUnderstanding, IntakeItem, IntakeItemType, WritingPlan
from app.services.intake.intake_services import InputUnderstandingService, IntakeItemService, WritingPlanService


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def count(self):
        return len(self._rows)


class _Db:
    def __init__(self, *, items=None, understandings=None, plans=None):
        self.items = list(items or [])
        self.understandings = list(understandings or [])
        self.plans = list(plans or [])
        self.added = []

    def query(self, model):
        if model is IntakeItem:
            return _Query(self.items)
        if model is InputUnderstanding:
            return _Query(self.understandings)
        if model is WritingPlan:
            return _Query(self.plans)
        return _Query([])

    def add(self, row):
        self.added.append(row)

    def flush(self):
        return None


class _Llm:
    def __init__(self, payload: dict):
        self.payload = payload
        self.messages = None

    def chat_completion(self, messages, **_kwargs):
        self.messages = messages
        return json.dumps(self.payload, ensure_ascii=False)


def _book():
    return SimpleNamespace(id=uuid4(), title="AI for Product Teams")


def _intake():
    return SimpleNamespace(
        id=uuid4(),
        creation_origin=CreationOrigin.idea_only,
        raw_goal_text="Write a practical book for product teams adopting AI.",
        negative_constraints_text="Avoid empty hype.",
        status=None,
    )


def test_input_understanding_requires_llm_intent_contract():
    intake = _intake()
    item = SimpleNamespace(
        intake_id=intake.id,
        item_type=IntakeItemType.natural_text,
        text_content="Use our onboarding notes and make every chapter practical.",
        parsed_preview=None,
    )
    db = _Db(items=[item])
    svc = InputUnderstandingService(db)  # type: ignore[arg-type]
    svc.llm = _Llm(
        {
            "user_facing_text": "You want a practical AI adoption book grounded in onboarding notes.",
            "summary_json": {"book_goal": "Practical AI adoption"},
            "intent_json": {
                "primary_intent": "idea_only",
                "book_promise": "Help teams adopt AI without hype.",
                "reader_outcome": "Plan safer AI workflows.",
                "source_usage_intent": "Use onboarding notes as chapter examples.",
                "must_influence": [
                    {
                        "input_ref": "onboarding notes",
                        "writing_effect": "turn notes into recurring chapter examples",
                        "applies_to": ["outline", "chapters", "review"],
                        "strength": "must",
                    }
                ],
            },
            "evidence_refs": [],
            "preserve_rules": [],
            "editable_rules": [],
            "avoid_rules": [],
            "unclear_questions": [],
        }
    )

    understanding = svc.generate(_book(), intake)

    assert understanding.summary_json["intent_json"]["must_influence"][0]["writing_effect"] == (
        "turn notes into recurring chapter examples"
    )
    assert "LLM" in svc.llm.messages[1]["content"]
    assert db.added == [understanding]


def test_input_understanding_rejects_missing_intent_contract():
    db = _Db()
    svc = InputUnderstandingService(db)  # type: ignore[arg-type]
    svc.llm = _Llm(
        {
            "user_facing_text": "A natural summary without intent.",
            "summary_json": {"book_goal": "Practical AI adoption"},
        }
    )

    with pytest.raises(ValueError, match="intent_json"):
        svc.generate(_book(), _intake())


def test_upload_role_detection_does_not_fallback_to_reference(monkeypatch):
    item = SimpleNamespace(detected_roles=None)
    db = _Db()

    class _FailingLlm:
        def chat_completion(self, *_args, **_kwargs):
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("app.services.intake.intake_services.LLMClient", _FailingLlm)

    IntakeItemService(db)._detect_roles(item, "usable content")  # type: ignore[arg-type]

    assert item.detected_roles == []


def test_upload_role_detection_ignores_empty_sample(monkeypatch):
    item = SimpleNamespace(detected_roles=None)
    db = _Db()

    class _UnexpectedLlm:
        def chat_completion(self, *_args, **_kwargs):
            raise AssertionError("should not call LLM without content")

    monkeypatch.setattr("app.services.intake.intake_services.LLMClient", _UnexpectedLlm)

    IntakeItemService(db)._detect_roles(item, "")  # type: ignore[arg-type]

    assert item.detected_roles == []


def test_upload_role_detection_filters_unknown_roles(monkeypatch):
    item = SimpleNamespace(detected_roles=None)
    db = _Db()

    class _LlmRoles:
        def chat_completion(self, *_args, **_kwargs):
            return json.dumps({"detected_roles": ["reference", "filename_guess", "goal"]})

    monkeypatch.setattr("app.services.intake.intake_services.LLMClient", _LlmRoles)

    IntakeItemService(db)._detect_roles(item, "chapter notes")  # type: ignore[arg-type]

    assert item.detected_roles == ["reference", "goal"]


def test_unreadable_upload_filename_not_sent_to_understanding_llm():
    secret_filename = "secret-outline-from-filename.docx"
    item = SimpleNamespace(
        intake_id=uuid4(),
        item_type=IntakeItemType.upload,
        text_content=f"[上传文件: {secret_filename}]",
        parsed_preview=None,
    )
    db = _Db(items=[item])
    svc = InputUnderstandingService(db)  # type: ignore[arg-type]
    svc.llm = _Llm(
        {
            "user_facing_text": "You uploaded a file, but its content is not available for intent analysis yet.",
            "summary_json": {"book_goal": "Clarify input"},
            "intent_json": {
                "primary_intent": "mixed",
                "book_promise": "Use only confirmed input.",
                "reader_outcome": "N/A",
                "source_usage_intent": "Do not infer file purpose without readable text.",
                "must_influence": [
                    {
                        "input_ref": "unreadable upload",
                        "writing_effect": "ask for confirmation before using this file as evidence",
                        "applies_to": ["outline", "review"],
                        "strength": "must",
                    }
                ],
            },
            "evidence_refs": [],
            "preserve_rules": [],
            "editable_rules": [],
            "avoid_rules": [],
            "unclear_questions": [],
        }
    )

    svc.generate(_book(), _intake())

    prompt = svc.llm.messages[1]["content"]
    assert secret_filename not in prompt
    assert "不要根据文件名或扩展名推断用途" in prompt


def test_writing_plan_persists_impact_map_from_llm():
    intent_json = {
        "primary_intent": "idea_only",
        "must_influence": [
            {
                "input_ref": "onboarding notes",
                "writing_effect": "turn notes into recurring chapter examples",
                "applies_to": ["outline", "chapters"],
                "strength": "must",
            }
        ],
    }
    understanding = SimpleNamespace(
        id=uuid4(),
        user_facing_text="You want a practical AI adoption book.",
        summary_json={"intent_json": intent_json},
    )
    db = _Db()
    svc = WritingPlanService(db)  # type: ignore[arg-type]
    svc.llm = _Llm(
        {
            "user_facing_text": "Write from real team decisions, not from generic AI commentary.",
            "plan_json": {
                "direction": "Practical AI adoption for product teams",
                "audience": "Product teams",
                "must_keep": ["Use concrete team examples"],
                "must_avoid": ["Avoid empty hype"],
            },
            "impact_map": {
                "outline": True,
                "narrative": True,
                "chapters": True,
                "review": True,
                "input_effects": [
                    {
                        "input_ref": "onboarding notes",
                        "writing_effect": "review must check every chapter uses at least one concrete example",
                        "applies_to": ["chapters", "review"],
                        "strength": "must",
                    }
                ],
            },
        }
    )

    plan = svc.generate(_book(), _intake(), understanding)

    assert plan.impact_map["review"] is True
    assert plan.impact_map["input_effects"][0]["writing_effect"].startswith("review must check")
    assert "意图契约" in svc.llm.messages[1]["content"]
    assert db.added == [plan]
