"""Tests for review agent service."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.review.review_agent_service import ReviewAgentService
from app.services.review.review_finding_validator import classify_product_dimension


def test_classify_product_dimension_mapping():
    assert classify_product_dimension({"category": "input_alignment"}) == "goal_alignment"
    assert classify_product_dimension({"dimension": "citation_sources"}) == "evidence_citation"


def test_build_task_summary_contains_standards():
    snap = {
        "must_avoid": ["不要营销腔"],
    }
    adopted = {
        "public_rules": True,
        "editorial_principles": True,
        "user_writing_basis": True,
    }
    summary = ReviewAgentService._render_summary_text(
        scope="book",
        chapter_indexes=None,
        adopted=adopted,
        exclusions=["ai_dash_heuristic"],
        custom_prompt=None,
        snap=snap,
    )
    assert "不要营销腔" in summary
    assert "公开出版规则" in summary
