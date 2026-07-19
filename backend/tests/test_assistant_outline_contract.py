"""Tests for assistant search LLM path + outline contract (no full source dump)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.assistant.search_intent_service import SearchIntent, prepare_search, refine_search_queries
from app.services.sources.source_outline_bridge import (
    materials_from_outline_contract,
    parse_chapters_from_text,
    prepare_outline_context,
)


def test_parse_chapters_from_text():
    chapters = parse_chapters_from_text("第一章 导论\n第二章 方法\n第三章 结论\n")
    assert len(chapters) == 3
    assert chapters[0]["title"] == "导论"
    assert chapters[1]["index"] == 2


def test_materials_empty_without_contract():
    book = SimpleNamespace(id=uuid4(), ai_inferred_settings={})
    db = MagicMock()
    mats = materials_from_outline_contract(db, book)
    assert mats["source_outline_blocks"] == []
    assert mats["source_requirement_blocks"] == []
    assert mats["source_manuscript_blocks"] == []
    assert mats["contract"] is None


def test_materials_from_prepare_contract_only():
    book_id = uuid4()
    seg_id = uuid4()
    book = SimpleNamespace(
        id=book_id,
        ai_inferred_settings={
            "confirmed_source_usages": {
                str(seg_id): {"usage": "primary_outline", "segment_type": "outline"},
            },
            "outline_generation_context": {
                "mode": "generate",
                "primary_ids": [str(seg_id)],
                "requirement_ids": [],
                "reference_outline_ids": [],
                "manuscript_policy": "omit",
                "manuscript_ids": [],
                "must_keep_chapter_titles": True,
            },
        },
    )
    seg = SimpleNamespace(
        id=seg_id,
        book_id=book_id,
        summary="第一章 导论\n第二章 方法",
        excerpt="",
        user_confirmed=True,
        segment_type=SimpleNamespace(value="outline"),
    )

    def _query(model):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = seg
        return q

    db = MagicMock()
    db.query.side_effect = _query

    mats = materials_from_outline_contract(db, book)
    assert mats["contract"] is not None
    assert mats["source_outline_blocks"]
    assert "导论" in mats["source_outline_blocks"][0]
    assert mats["source_manuscript_blocks"] == []


def test_prepare_outline_context_persists_settings():
    book = SimpleNamespace(id=uuid4(), ai_inferred_settings={"confirmed_source_usages": {}})
    db = MagicMock()
    contract = prepare_outline_context(
        db,
        book,
        manuscript_policy="omit",
        primary_segment_ids=[],
        requirement_segment_ids=[],
    )
    assert contract["manuscript_policy"] == "omit"
    assert book.ai_inferred_settings["outline_generation_context"]["mode"] == "generate"


@patch("app.services.assistant.search_intent_service.LLMClient")
def test_prepare_search_uses_llm_not_regex_path(mock_llm_cls):
    client = MagicMock()
    mock_llm_cls.return_value = client
    client.chat_completion.side_effect = [
        '{"search_type":"person_works","person_name":"沈阳","person_name_raw":"沈阳教授",'
        '"institution":"清华大学","role":"教授","topic":null,"language":["zh","en"],'
        '"source_types":["academic"],"require_author_match":true,"needs_disambiguation":false,'
        '"display_query":"清华大学沈阳教授"}',
        '{"refined_queries":["清华大学 沈阳 教授","Shenyang Tsinghua","沈阳 著作"]}',
    ]
    out = prepare_search("查清华大学沈阳教授作品", search_type_hint="person_works")
    assert out["intent"]["person_name"] == "沈阳"
    assert out["intent"]["institution"] == "清华大学"
    assert out["queries"][0].startswith("清华大学")
    assert client.chat_completion.call_count == 2


@patch("app.services.assistant.external_search_service.search_semantic_scholar", return_value=[])
@patch("app.services.assistant.external_search_service.search_crossref", return_value=[])
@patch("app.services.assistant.external_search_service.search_arxiv", return_value=[])
@patch("app.services.assistant.external_search_service.search_wikipedia", return_value=[])
@patch("app.services.assistant.external_search_service._duckduckgo_lite", return_value=[])
@patch("app.services.assistant.external_search_service.LiteratureAgent")
def test_search_person_works_uses_provided_queries(
    mock_agent_cls,
    _ddg,
    _wiki,
    _arxiv,
    _xref,
    _ss,
):
    from app.services.assistant.external_search_service import ExternalSearchService

    mock_agent_cls.return_value.search.return_value = []
    intent = SearchIntent(
        search_type="person_works",
        person_name="沈阳",
        institution="清华大学",
        role="教授",
        display_query="清华大学沈阳教授",
        raw_query="查清华大学沈阳教授作品",
    )
    queries = ["清华大学 沈阳 教授", "沈阳 publications"]
    with patch(
        "app.services.assistant.external_search_service.prepare_search"
    ) as prep:
        result = ExternalSearchService().search_person_works(
            "沈阳",
            intent=intent,
            queries=queries,
            prepare_if_missing=False,
        )
        prep.assert_not_called()
    assert result["queries"] == queries
    assert result["search_intent"]["person_name"] == "沈阳"


def test_person_queries_no_forced_english_fillers():
    intent = SearchIntent(
        search_type="person_works",
        person_name="张三",
        display_query="张三",
        raw_query="张三",
    )
    with patch("app.services.assistant.search_intent_service.LLMClient") as mock_cls:
        mock_cls.return_value.chat_completion.return_value = (
            '{"refined_queries":["张三","张三 著作","张三 论文"]}'
        )
        qs = refine_search_queries(intent)
    assert all("machine learning" not in q.lower() for q in qs)
    assert len([q for q in qs if any("a" <= c.lower() <= "z" for c in q)]) <= 3


def test_stage_whitelist_outline_drops_manuscript_without_policy():
    from app.services.writing.writing_context_builder import WritingContextBuilder

    wcb = WritingContextBuilder(MagicMock())
    snap = {
        "book_id": str(uuid4()),
        "writing_basis_id": None,
        "source_outline_blocks": ["第一章"],
        "source_manuscript_blocks": ["很长的初稿" * 100],
        "source_requirement_blocks": ["必须遵守"],
        "outline_contract": {"manuscript_policy": "omit"},
        "requirements": [],
        "must_keep": [],
        "must_avoid": [],
        "material_policy": [],
        "outline_policy": [],
    }
    out = wcb.apply_stage_whitelist(snap, "outline")
    assert out["source_outline_blocks"] == ["第一章"]
    assert out["source_manuscript_blocks"] == []


def test_critic_no_rule_patch_or_full_dump_markers():
    """Critic self-check: core files must not reintroduce dump/rule-primary paths."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    outline_router = (root / "routers" / "outline.py").read_text(encoding="utf-8")
    auto_job = (root / "services" / "auto_book_job.py").read_text(encoding="utf-8")
    external = (root / "services" / "assistant" / "external_search_service.py").read_text(encoding="utf-8")
    startup = (root / "prompts" / "assistant" / "startup_system.py").read_text(encoding="utf-8")

    assert "collect_assistant_source_context" not in outline_router
    assert "collect_assistant_source_context" not in auto_job
    assert "materials_from_outline_contract" in outline_router
    assert "prepare_search" in external or "SearchIntent" in external
    assert "唯一正式书稿设定" in startup or "book_settings" in startup
    assert "outline_route" in startup
    assert "search_sources" in startup
    assert "reader_outcome" not in startup or "不得要求用户填写" in startup
