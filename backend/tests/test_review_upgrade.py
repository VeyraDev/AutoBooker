from types import SimpleNamespace

import pytest

from app.services.figure_lint import lint_figures
from app.services.review_anchor import locate_issue_anchor, snapshot_hash
from app.services.review_apply import preview_issue_application, validate_replacement_text
from app.services.review_scoring import REVIEW_DIMENSIONS, aggregate_review


def test_aggregate_review_uses_fixed_dimensions_and_ignores_resolved_dismissed_stale():
    detector_dimensions = {
        key: {"raw_score": 90, "summary": "", "status": "completed", "detector": "test"}
        for key in REVIEW_DIMENSIONS
    }
    issues = [
        {"dimension": "language_grammar", "issue_type": "grammar", "severity": "medium", "penalty": 6, "status": "open"},
        {"dimension": "language_grammar", "issue_type": "typo", "severity": "high", "penalty": 10, "status": "resolved"},
        {"dimension": "language_grammar", "issue_type": "typo", "severity": "high", "penalty": 10, "status": "dismissed"},
        {"dimension": "language_grammar", "issue_type": "typo", "severity": "high", "penalty": 10, "status": "stale"},
    ]

    rows, total, status = aggregate_review(detector_dimensions, issues)

    assert len(rows) == 7
    grammar = next(row for row in rows if row["key"] == "language_grammar")
    assert grammar["effective_score"] == 84
    assert grammar["issue_count"] == 1
    assert total > 80
    assert status == "completed"


def test_detector_failure_is_excluded_from_total_score():
    detector_dimensions = {
        key: {"raw_score": 80, "summary": "", "status": "completed", "detector": "test"}
        for key in REVIEW_DIMENSIONS
    }
    detector_dimensions["citation_sources"] = {"raw_score": 0, "summary": "", "status": "unavailable", "detector": "citation_lint"}

    rows, total, status = aggregate_review(detector_dimensions, [])

    assert next(row for row in rows if row["key"] == "citation_sources")["status"] == "unavailable"
    assert total == 80
    assert status == "partial"


def test_anchor_prefers_paragraph_id_when_quote_repeats():
    md = """<!-- pid:p_one -->
重复文本需要修改。

<!-- pid:p_two -->
重复文本需要修改。"""

    located = locate_issue_anchor(md, quote="重复文本", paragraph_id="p_two")

    assert located.paragraph_id == "p_two"
    assert located.paragraph_index == 1
    assert located.strategy == "paragraph_id_quote"


def test_replacement_text_rejects_instructional_prefixes():
    with pytest.raises(ValueError):
        validate_replacement_text("replace", "建议改为：这是一句最终正文")

    assert validate_replacement_text("replace", "这是一句最终正文") == "这是一句最终正文"


def test_preview_application_blocks_stale_low_confidence_only_as_preview():
    md = "第一段。\n\n第二段需要修改。"
    old_hash = snapshot_hash("旧正文")

    preview = preview_issue_application(
        current_markdown=md,
        issue_snapshot_hash=old_hash,
        quote="第二段需要修改。",
        action_type="replace",
        replacement_text="第二段已经修改。",
    )

    assert preview["stale"] is True
    assert preview["preview_required"] is True
    assert preview["diff"]["before"] == "第二段需要修改。"


def test_figure_lint_handles_no_figures_as_not_applicable():
    result = lint_figures("纯文字章节。", [])

    assert result["dimension"] == "figure_quality"
    assert result["status"] == "not_applicable"
    assert result["raw_score"] == 100
    assert result["issues"] == []


def test_figure_lint_reports_missing_caption_and_source():
    fig = SimpleNamespace(
        figure_number="1-1",
        caption="",
        raw_annotation="",
        file_path="",
        file_url="",
    )

    result = lint_figures("见图1-1。", [fig])

    issue_types = {issue["issue_type"] for issue in result["issues"]}
    assert "missing_caption" in issue_types
