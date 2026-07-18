"""Tests for project-level review rule regression gate."""

from __future__ import annotations

import pytest

from app.services.review.review_rule_regression import (
    ensure_review_rule_regression_gate_passed,
    run_review_rule_regression_gate,
)


def test_rule_regression_gate_runs_review_quality_fixture_and_reports_direct_coverage():
    result = run_review_rule_regression_gate(
        rule_candidate={
            "product_dimension": "structure_progress",
            "issue_type": "paragraph_echo",
            "fix_capability": "preview_apply",
        },
        rule_text="同一小节重复绕回同一结论时，应优先提示合并重复表达。",
    )

    assert result["status"] == "passed"
    assert result["coverage_status"] == "direct"
    assert result["auto_case_count"] >= 4
    assert "paragraph_adjacent_echo_preview_merge" in result["related_case_ids"]
    assert result["failed_case_ids"] == []


def test_rule_regression_gate_blocks_ai_rate_contract_conflict():
    result = run_review_rule_regression_gate(
        rule_candidate={
            "product_dimension": "argument_quality",
            "issue_type": "generic_summary",
            "fix_capability": "preview_apply",
        },
        rule_text="遇到空泛总结时输出 AI率 百分比，帮助用户判断是否需要改。",
    )

    assert result["status"] == "failed"
    assert result["conflicts"]
    assert result["conflicts"][0]["rule_id"] == "ai.no_ai_rate_percentage.v1"

    with pytest.raises(ValueError, match="regression gate failed"):
        ensure_review_rule_regression_gate_passed(
            rule_candidate={
                "product_dimension": "argument_quality",
                "issue_type": "generic_summary",
                "fix_capability": "preview_apply",
            },
            rule_text="遇到空泛总结时输出 AI率 百分比，帮助用户判断是否需要改。",
        )
