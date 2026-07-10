"""WritingContextBuilder unit tests (no DB)."""

from __future__ import annotations

from app.services.writing.writing_context_builder import WritingContextBuilder


class _NoDb:
    pass


def test_context_hash_changes_when_must_avoid_changes():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    snap1 = {
        "understanding_id": "u1",
        "writing_plan_id": "p1",
        "requirement_ids": ["r1"],
        "outline_constraint_ids": [],
        "must_avoid": ["不要口语化"],
        "must_keep": [],
        "chapter_index": None,
    }
    snap2 = {**snap1, "must_avoid": ["不要学术黑话"]}
    assert wcb.context_hash(snap1) != wcb.context_hash(snap2)


def test_fallback_legacy_user_material_without_plan():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    snap = {
        "understanding_id": None,
        "writing_plan_id": None,
        "requirements": [],
        "must_keep": [],
        "must_avoid": [],
        "material_policy": [],
        "material_terms": [],
        "legacy_user_material": "用户原始资料",
        "plan_text": "",
        "understanding_text": "",
    }
    block = wcb.to_prompt_block(snap)
    assert "用户原始资料" in block


def test_prompt_block_includes_intent_effects():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    snap = {
        "understanding_text": "The book should be practical.",
        "plan_text": "Use real decisions as examples.",
        "intent_effects": [
            {
                "input_ref": "onboarding notes",
                "writing_effect": "turn notes into recurring chapter examples",
                "applies_to": ["outline", "chapters", "review"],
            }
        ],
        "must_keep": [],
        "must_avoid": [],
        "material_policy": [],
        "requirements": [],
        "material_terms": [],
        "legacy_user_material": "",
    }

    block = wcb.to_prompt_block(snap)

    assert "onboarding notes -> turn notes into recurring chapter examples" in block
    assert "outline" in block


def test_context_hash_changes_when_intent_effect_changes():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    base = {
        "understanding_id": "u1",
        "writing_plan_id": "p1",
        "requirement_ids": [],
        "outline_constraint_ids": [],
        "must_avoid": [],
        "must_keep": [],
        "intent_json": {"primary_intent": "idea_only"},
        "impact_map": {"outline": True},
        "intent_effects": [{"writing_effect": "use practical examples"}],
        "chapter_index": None,
    }
    changed = {**base, "intent_effects": [{"writing_effect": "use cautionary examples"}]}

    assert wcb.context_hash(base) != wcb.context_hash(changed)
