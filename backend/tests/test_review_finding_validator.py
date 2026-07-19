"""Tests for review finding validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.review.review_finding_validator import (
    check_locatable,
    classify_product_dimension,
    route_finding_fix,
    severity_to_tier,
    validate_finding,
)
from app.services.review.review_rule_library import match_basis_refs

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "review" / "sample_cases.json"


def test_figure_caption_ai_signature_filtered():
    finding = {
        "quote": "图1-1 系统架构",
        "detector": "ai_detect_v1",
        "dimension": "ai_signature",
        "severity": "high",
    }
    assert validate_finding(finding) is None


def test_no_quote_high_severity_downgraded_to_observe():
    finding = {"quote": "", "severity": "high", "title": "结构问题", "dimension": "structure"}
    out = validate_finding(finding)
    assert out is not None
    assert severity_to_tier(out["severity"]) == "observe"


def test_must_fix_requires_locatable_in_chapter():
    finding = {
        "quote": "不存在的内容",
        "severity": "high",
        "dimension": "logic",
        "title": "问题",
    }
    out = validate_finding(finding, chapter_md="完全不同的正文")
    assert out is not None
    assert severity_to_tier(out["severity"]) != "must_fix"


def test_locatable_quote():
    md = "首段文字。由此可见，后文继续。"
    assert check_locatable({"quote": "由此可见"}, chapter_md=md) is True


def test_must_avoid_basis_refs_from_context():
    finding = {"category": "input_alignment", "detail": "违反用户要求：不要营销腔", "title": "营销腔"}
    snap = {"must_avoid": ["不要营销腔", "避免夸张形容词"]}
    refs = match_basis_refs(finding, snap)
    assert any("不要营销腔" in r for r in refs)


def test_classify_product_dimension():
    assert classify_product_dimension({"category": "copyediting"}) == "publication_delivery"


def test_data_evidence_defaults_to_needs_verification():
    finding = {
        "quote": "岗位时间中约有40%到60%用于沟通",
        "severity": "high",
        "dimension": "citation_sources",
        "issue_type": "missing_citation",
        "title": "断言缺少来源",
        "detail": "百分比无来源",
    }
    out = validate_finding(finding)
    assert out is not None
    assert out["tier"] == "needs_verification"
    assert out["title"] == "具体比例缺少可核验来源"
    assert out.get("action_options")
    assert out.get("why_it_matters") in ("", None) or out.get("why_it_matters") != out.get("detail")


def test_fix_router_adds_actions_after_detection_without_replacement():
    routed = route_finding_fix(
        {
            "dimension": "ai_signature",
            "issue_type": "generic_summary",
            "severity": "medium",
            "quote": "综上所述，这既是机遇也是挑战。",
        }
    )

    assert routed["fix_capability"] == "preview_apply"
    assert routed["action_type"] == "revise"
    assert routed["replacement_text"] == ""
    assert routed["action_options"][0]["id"] == "preview_fix"


def test_fix_router_keeps_evidence_issue_as_choice_not_auto_rewrite():
    routed = route_finding_fix(
        {
            "dimension": "citation_sources",
            "issue_type": "missing_citation",
            "severity": "needs_verification",
            "quote": "数据显示增长了60%。",
        }
    )

    assert routed["fix_capability"] == "choice_then_apply"
    assert routed["action_type"] == "choose"
    assert routed["replacement_text"] == ""
    assert {option["id"] for option in routed["action_options"]} == {
        "add_source",
        "mark_estimate",
        "remove_number",
    }


def test_why_it_matters_not_copied_from_detail():
    from app.services.review.review_finding_validator import enrich_finding_metadata

    item = enrich_finding_metadata(
        {"title": "问题", "detail": "说明A", "quote": "原文", "severity": "medium", "dimension": "grammar"}
    )
    assert item["why_it_matters"] == ""


def test_publication_claim_requires_rule_id():
    finding = {
        "quote": "数据表明增长20%",
        "severity": "high",
        "dimension": "citation_sources",
        "issue_type": "missing_citation",
        "title": "违反出版规范",
        "detail": "出版规范要求具体数据必须标注来源",
    }
    out = validate_finding(finding)
    assert out is not None
    assert out["tier"] != "must_fix"
    assert out.get("ungrounded_publication_claim") or out["tier"] == "needs_verification"


def test_compound_person_query_parsed_generically():
    from app.services.assistant.person_search_intent import (
        build_person_queries,
        build_person_search_intent,
        parse_compound_person_query,
    )

    name, inst, role = parse_compound_person_query("清华大学沈阳教授")
    assert name == "沈阳"
    assert inst == "清华大学"
    assert role == "教授"

    intent = build_person_search_intent("清华大学沈阳教授")
    assert intent.person_name == "沈阳"
    assert intent.institution == "清华大学"
    assert intent.role == "教授"
    assert "清华大学" in intent.display_query
    qs = build_person_queries(intent)
    assert qs[0] == intent.display_query or "清华大学" in qs[0]


def test_rank_prefers_person_entity_over_geo_page():
    from app.services.assistant.person_author_rank import rank_works_for_person
    from app.services.assistant.person_search_intent import build_person_search_intent

    intent = build_person_search_intent("张三", institution="北京大学")
    works = [
        {
            "title": "张三",
            "authors": [],
            "abstract_preview": "张三是某地级市行政区划名称，人口与平方公里统计",
            "source": "wikipedia",
        },
        {
            "title": "传播学研究",
            "authors": ["张三"],
            "abstract_preview": "北京大学新闻学院教授，研究方向为新媒体",
            "source": "openalex",
            "journal": "Journal",
            "year": 2020,
            "url": "https://example.com",
        },
    ]
    ranked = rank_works_for_person(works, intent)
    assert ranked
    assert ranked[0]["authors"] == ["张三"]
    assert float(ranked[0].get("person_rank_score") or 0) > float(
        next((w.get("person_rank_score") or -99) for w in ranked if "行政区划" in str(w.get("abstract_preview")))
        if any("行政区划" in str(w.get("abstract_preview")) for w in ranked)
        else -99
    )


def test_collect_assistant_source_context_parses_outline():
    from app.services.sources.source_outline_bridge import _parse_chapters_from_text

    chapters = _parse_chapters_from_text("第一章 导论\n第二章 方法\n第三章 结论\n")
    assert len(chapters) == 3
    assert chapters[0]["title"] == "导论"
    assert chapters[1]["index"] == 2



@pytest.mark.parametrize("case", json.loads(_FIXTURES.read_text(encoding="utf-8")))
def test_sample_cases(case: dict):
    finding = case["input"]
    chapter_md = case.get("chapter_md")
    result = validate_finding(finding, chapter_md=chapter_md)
    expected = case["expected"]
    if expected == "drop":
        assert result is None
    elif expected == "observe":
        assert result is not None
        assert severity_to_tier(result.get("severity")) == "observe"
    else:
        assert result is not None
