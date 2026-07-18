"""Book classification from creative intent — not create-time 大众非虚构 default."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.models.book import BookType
from app.services.writing.project_seed import (
    _pair_type_and_style,
    infer_and_apply_book_settings,
    is_provisional_classification,
    mark_classification_source,
)


def _book(**overrides):
    data = {
        "id": uuid4(),
        "title": "书稿1",
        "book_type": BookType.nonfiction,
        "style_type": "popular_science",
        "discipline": None,
        "disciplines": None,
        "target_audience": None,
        "topic_tags": None,
        "topic_brief": "面向研究生的智能体记忆系统研究报告",
        "user_material": None,
        "citation_style": None,
        "target_words": 80000,
        "ai_inferred_settings": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_provisional_classification_detects_create_default():
    book = _book()
    assert is_provisional_classification(book) is True
    mark_classification_source(book, "inferred")
    assert is_provisional_classification(book) is False


def test_pair_type_prefers_academic_style_over_nonfiction_label():
    bt, st = _pair_type_and_style(
        "nonfiction",
        "technical_deep_dive",
        fallback_type=BookType.nonfiction,
        fallback_style="popular_science",
    )
    assert bt == BookType.academic
    assert st == "technical_deep_dive"


def test_infer_overrides_provisional_popular_science(monkeypatch):
    payload = {
        "book_type": "academic",
        "style_type": "technical_deep_dive",
        "target_words": 180000,
        "target_audience": "研究生与科研人员",
        "disciplines": ["计算机科学"],
        "discipline_candidates": [{"name": "计算机科学", "reason": "术语与证据标准"}],
        "topic_tags": ["智能体记忆"],
        "citation_style": "gb_t7714",
        "topic_brief": "研究报告取向",
        "classification_reason": "课题研究报告，应属学术技术深度",
    }

    class _Client:
        def chat_completion(self, *_args, **_kwargs):
            return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr("app.services.writing.project_seed.LLMClient", lambda: _Client())
    book = _book()
    assert is_provisional_classification(book)
    infer_and_apply_book_settings(book, "test-model")
    assert book.book_type == BookType.academic
    assert book.style_type == "technical_deep_dive"
    assert book.ai_inferred_settings["classification_source"] == "inferred"
    assert is_provisional_classification(book) is False


def test_startup_prompt_requires_classification_rewrite():
    from app.prompts.assistant.startup_system import turn_output_instruction

    text = turn_output_instruction()
    assert "书类识别" in text
    assert "大众非虚构" in text
    assert "禁止无脑沿用" in text
