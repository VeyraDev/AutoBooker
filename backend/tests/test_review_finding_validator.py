"""Tests for review finding validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.review.review_finding_validator import (
    check_locatable,
    classify_product_dimension,
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
