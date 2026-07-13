"""Tests for custom review service helpers."""

from __future__ import annotations

from app.services.review.review_finding_validator import classify_product_dimension, validate_finding


def test_custom_review_finding_classified():
    raw = {
        "category": "custom_review",
        "severity": "medium",
        "title": "可能跑题",
        "detail": "本章偏离安装主题",
        "quote": "此外，行业趋势表明",
    }
    assert classify_product_dimension(raw) == "goal_alignment"
    out = validate_finding(raw, chapter_md="此外，行业趋势表明需要关注。")
    assert out is not None
