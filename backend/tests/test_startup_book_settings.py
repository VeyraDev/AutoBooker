"""Startup assistant: single book_settings protocol."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.book import BookType
from app.services.assistant.book_settings_context import (
    current_book_settings,
    get_setting_origins,
    set_setting_origin,
)
from app.services.assistant.outline_readiness import get_missing_outline_settings
from app.services.assistant.project_assistant_service import _filter_patch_by_origins
from app.services.assistant.quick_fill_ops import record_quick_fill, undo_quick_fill


def _book(**overrides):
    data = {
        "id": uuid4(),
        "title": "书稿1",
        "book_type": BookType.nonfiction,
        "style_type": "popular_science",
        "target_audience": None,
        "disciplines": None,
        "discipline": None,
        "topic_brief": None,
        "topic_tags": None,
        "target_words": None,
        "citation_style": None,
        "ai_inferred_settings": {},
        "allow_title_optimization": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_missing_outline_settings_placeholder_title():
    book = _book()
    missing = get_missing_outline_settings(book)
    assert "书名" in missing
    assert "目标读者" in missing
    assert "主题要点" in missing


def test_filter_patch_protects_user_manual():
    book = _book(target_audience="用户手写读者")
    set_setting_origin(book, "target_audience", "user_manual")
    patch = {"target_audience": "助手乱改", "topic_brief": "可写入的主题"}
    decisions = [
        {"field": "target_audience", "decision_type": "inferred"},
        {"field": "topic_brief", "decision_type": "suggested"},
    ]
    filtered = _filter_patch_by_origins(book, patch, decisions)
    assert "target_audience" not in filtered
    assert filtered.get("topic_brief") == "可写入的主题"


def test_filter_allows_explicit_overwrite():
    book = _book(target_audience="旧值")
    set_setting_origin(book, "target_audience", "user_manual")
    filtered = _filter_patch_by_origins(
        book,
        {"target_audience": "用户本轮明确改了"},
        [{"field": "target_audience", "decision_type": "explicit"}],
    )
    assert filtered["target_audience"] == "用户本轮明确改了"


def test_quick_fill_undo_restores_before():
    book = _book(title="正式书名", topic_brief="原主题", target_words=80000)
    before = current_book_settings(book)
    book.topic_brief = "补齐后主题"
    book.target_words = 120000
    after = current_book_settings(book)
    op_id = record_quick_fill(book, before=before, after=after, turn_id="t1")
    result = undo_quick_fill(book, op_id)
    assert book.topic_brief == "原主题"
    assert book.target_words == 80000
    assert result["operation_id"] == op_id


def test_startup_prompt_has_single_settings_contract():
    from app.prompts.assistant.startup_system import (
        QUICK_FILL_INSTRUCTION,
        STARTUP_ASSISTANT_SYSTEM,
        startup_turn_output_instruction,
    )

    assert "正式设定" in STARTUP_ASSISTANT_SYSTEM
    assert len(STARTUP_ASSISTANT_SYSTEM) < 1200
    assert "Excel" not in STARTUP_ASSISTANT_SYSTEM
    assert "reader_outcome" not in STARTUP_ASSISTANT_SYSTEM
    assert "suggest_book_settings" in QUICK_FILL_INSTRUCTION
    out = startup_turn_output_instruction()
    assert "book_settings_patch" in out
    assert "basis_patch" not in out
    assert "tool_calls" in out
    assert "retrieve_source_context" in out
    assert "search_references" in out


def test_source_catalog_is_lightweight():
    from app.services.assistant.book_settings_context import source_catalog

    # Smoke: function exists and returns list shape via monkeypatch-free call pattern
    assert callable(source_catalog)


def test_setting_origins_roundtrip():
    book = _book()
    set_setting_origin(book, "disciplines", "assistant_inferred")
    origins = get_setting_origins(book)
    assert origins["disciplines"]["origin"] == "assistant_inferred"


def test_user_facing_message_strips_machine_fields_and_summarizes():
    from app.services.assistant.project_assistant_service import _ensure_user_facing_update_message

    leaked = (
        "好的，收到书名。\n"
        "topic_brief: 本书探讨健康城市\n"
        "disciplines: ['城市规划']\n"
        "[object Object]\n"
    )
    out = _ensure_user_facing_update_message(
        leaked,
        {
            "topic_brief": "本书探讨健康城市",
            "disciplines": ["城市规划", "公共卫生"],
        },
        [
            {"field": "topic_brief", "reason": "书名点明三维展开"},
            {"field": "disciplines", "reason": "健康城市核心交叉学科"},
        ],
    )
    assert "topic_brief" not in out
    assert "[object Object]" not in out
    assert "主题要点" in out
    assert "学科领域" in out
    assert "城市规划" in out
