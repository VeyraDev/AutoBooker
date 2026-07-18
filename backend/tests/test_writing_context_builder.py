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
        "writing_basis_id": None,
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


def test_prompt_block_prefers_writing_basis():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    snap = {
        "writing_basis_id": "b1",
        "writing_basis": {
            "direction": "Practical AI book",
            "book_promise": "Help teams ship safely",
            "target_readers": "Product teams",
            "material_policy": ["Use onboarding notes"],
            "outline_policy": [],
            "citation_policy": [],
            "figure_policy": [],
        },
        "understanding_text": "Old understanding text",
        "plan_text": "Old plan text",
        "must_keep": [],
        "must_avoid": [],
        "material_policy": [],
        "requirements": [],
        "material_terms": [],
        "legacy_user_material": "",
    }
    block = wcb.to_prompt_block(snap)
    assert "【写作依据】" in block
    assert "Practical AI book" in block
    assert "Old understanding text" not in block


def test_context_hash_changes_when_writing_basis_id_changes():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    snap1 = {
        "writing_basis_id": "b1",
        "understanding_id": "u1",
        "writing_plan_id": "p1",
        "requirement_ids": [],
        "outline_constraint_ids": [],
        "must_avoid": [],
        "must_keep": [],
        "chapter_index": None,
    }
    snap2 = {**snap1, "writing_basis_id": "b2"}
    assert wcb.context_hash(snap1) != wcb.context_hash(snap2)


def test_prompt_block_includes_citation_verification_summary():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    snap = {
        "must_keep": [],
        "must_avoid": [],
        "material_policy": [],
        "requirements": [],
        "material_terms": [],
        "legacy_user_material": "",
        "citations": [
            {
                "title": "对强人工智能及其理论预设的考察",
                "authors": ["王佳", "朱敏"],
                "year": 2010,
                "verification_status": "needs_verification",
                "missing_fields": ["abstract"],
                "recommended_search_query": "对强人工智能及其理论预设的考察 王佳 2010",
            }
        ],
    }

    block = wcb.to_prompt_block(snap)

    assert "【本书文献与核验状态】" in block
    assert "核验：needs_verification" in block
    assert "缺字段：abstract" in block
    assert "建议检索：对强人工智能及其理论预设的考察 王佳 2010" in block


def test_context_hash_changes_when_citation_verification_changes():
    wcb = WritingContextBuilder(_NoDb())  # type: ignore[arg-type]
    base = {
        "writing_basis_id": None,
        "understanding_id": "u1",
        "writing_plan_id": "p1",
        "requirement_ids": [],
        "outline_constraint_ids": [],
        "must_avoid": [],
        "must_keep": [],
        "chapter_index": None,
        "citations": [{"title": "文献A", "verification_status": "needs_verification"}],
    }
    changed = {**base, "citations": [{"title": "文献A", "verification_status": "verified"}]}

    assert wcb.context_hash(base) != wcb.context_hash(changed)
