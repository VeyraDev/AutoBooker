"""Tests for deterministic review quality reviewers."""

from __future__ import annotations

from types import SimpleNamespace

from app.prompts.review_quality import get_review_prompt_asset, list_review_prompt_assets
from app.services.review.quality_reviewers import run_book_quality_review, run_chapter_quality_review
from app.services.review.review_finding_validator import enrich_finding_metadata, validate_finding
from app.services.review.review_workspace_service import _batch_preview_skip_reason


def _book(book_type: str = "practical_guide"):
    return SimpleNamespace(title="AI自动化写书终极秘籍：从选题到出版一套全流程秒懂实战指南", book_type=book_type)


def _chapter(title: str, index: int = 1):
    return SimpleNamespace(index=index, title=title, content={"text": ""})


def test_prompt_registry_exposes_review_assets():
    keys = {asset.key for asset in list_review_prompt_assets()}
    assert "ai_text_risk_detector" in keys
    assert "title_reviewer" in keys
    assert "reference_authenticity_reviewer" in keys
    prompt = get_review_prompt_asset("ai_text_risk_detector").prompt
    assert "AI" in prompt and "百分比" in prompt


def test_quality_reviewers_detect_title_echo_reference_layout_and_ai_risk():
    md = """
人工智能正在改变知识生产方式，它不仅影响工具，也影响人们理解世界的方式。

人工智能正在重塑知识生产方式，它不仅改变工具，也改变我们理解世界的方式。

90% of teams spend more than half of their planning time on coordination.

图1-1 模型结构

图1-3 调用链路

图1-2 数据流

综上所述，人工智能的发展对于企业来说既是机遇也是挑战。我们需要全面、系统、深入地理解这一变化，并在实践中不断探索。
""".strip()
    result = run_chapter_quality_review(
        _book(),
        _chapter("AI自动化写书终极秘籍：从选题到出版一套全流程秒懂实战指南"),
        md,
        {},
    )
    issue_types = {item["issue_type"] for item in result.issues}
    assert "title_marketing_or_too_long" in issue_types
    assert "paragraph_adjacent_echo" in issue_types or "paragraph_near_duplicate" in issue_types
    assert "missing_citation" in issue_types
    assert "figure_table_numbering" in issue_types
    assert "generic_summary" in issue_types


def test_quality_reviewer_metadata_survives_validator():
    md = "90% of teams spend more than half of their planning time on coordination."
    result = run_chapter_quality_review(_book(), _chapter("章节标题"), md, {})
    finding = next(item for item in result.issues if item["issue_type"] == "missing_citation")
    enriched = enrich_finding_metadata(finding, {}, chapter_md=md)
    validated = validate_finding(enriched, chapter_md=md)
    assert validated is not None
    assert validated["tier"] == "needs_verification"
    assert validated["fix_capability"] == "choice_then_apply"
    assert validated["product_dimension"] == "evidence_citation"
    assert {item["id"] for item in validated["action_options"]} >= {"add_source", "mark_estimate", "remove_number"}


def test_batch_preview_only_accepts_low_risk_locatable_preview_apply_items():
    eligible = SimpleNamespace(
        status="open",
        applied_at=None,
        resolved_at=None,
        quality_evidence={"fix_capability": "preview_apply"},
        char_start=0,
        paragraph_id=None,
        paragraph_index=None,
        quote="original",
    )
    assert _batch_preview_skip_reason(eligible) is None

    choice_required = SimpleNamespace(
        **{**eligible.__dict__, "quality_evidence": {"fix_capability": "choice_then_apply"}}
    )
    assert _batch_preview_skip_reason(choice_required) == "not_preview_apply"

    unlocatable = SimpleNamespace(
        **{**eligible.__dict__, "char_start": None, "quote": "", "paragraph_index": None}
    )
    assert _batch_preview_skip_reason(unlocatable) == "not_locatable"

    pending_recheck = SimpleNamespace(**{**eligible.__dict__, "applied_at": object()})
    assert _batch_preview_skip_reason(pending_recheck) == "not_open"


def test_book_quality_review_flags_uploaded_academic_reference_without_abstract():
    context = {
        "citations": [
            {
                "title": "人工智能教育应用研究",
                "authors": ["张三"],
                "year": 2024,
                "journal": "现代教育技术",
                "document_type": "journal_article",
                "metadata_status": "needs_completion",
                "source": "uploaded_file",
                "has_abstract": False,
            },
            {
                "title": "智能体协作综述",
                "authors": ["李四"],
                "year": 2023,
                "journal": "计算机研究",
                "document_type": "journal_article",
                "metadata_status": "complete",
                "source": "uploaded_file",
                "has_abstract": True,
            },
        ]
    }

    findings = run_book_quality_review(_book(), [], context)

    ref_findings = [item for item in findings if item["issue_type"] == "reference_metadata_incomplete"]
    assert len(ref_findings) == 1
    assert ref_findings[0]["quote"] == "人工智能教育应用研究"
    assert ref_findings[0]["fix_capability"] == "choice_then_apply"
    assert ref_findings[0]["verification_status"] == "needs_verification"
