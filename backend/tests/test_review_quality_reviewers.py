"""Tests for deterministic review quality reviewers."""

from __future__ import annotations

from types import SimpleNamespace

from app.prompts.review_quality import get_review_prompt_asset, list_review_prompt_assets
from app.services.review.quality_reviewers import run_book_quality_review, run_chapter_quality_review
from app.services.review.review_finding_validator import enrich_finding_metadata, validate_finding
from app.services.review.review_workspace_service import ReviewWorkspaceService
from app.services.review.review_workspace_service import _batch_preview_skip_reason
from app.services.review.title_benchmarks import extract_title_from_document_name, title_benchmark_for_style


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
    assert "AI" in prompt and "不输出 AI 率" in prompt


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
    title_issue = next(item for item in result.issues if item["issue_type"] == "title_marketing_or_too_long")
    assert "常见区间" in title_issue["detail"]
    assert "title_benchmark" in title_issue["quality_evidence"]
    assert "paragraph_adjacent_echo" in issue_types or "paragraph_near_duplicate" in issue_types
    assert "missing_citation" in issue_types
    assert "figure_table_numbering" in issue_types
    assert "generic_summary" in issue_types
    ai_issue = next(item for item in result.issues if item["issue_type"] == "generic_summary")
    assert ai_issue["action"] == "revise"
    assert ai_issue["replacement_text"] == ""
    assert ai_issue["fix_capability"] == "preview_apply"


def test_title_benchmark_uses_document_filenames(tmp_path):
    names = [
        "《AI文明史·前史》张笑宇【文字版_PDF电子书_雅书】.txt",
        "1015321785-AI工程-大模型应用开发实战-越-奇普-萱-文字版-PDF电子书-雅书.txt",
        "Claude-Code-Complete-Guide-zh-v260411.txt",
        "_classification_result.txt",
    ]
    for name in names:
        (tmp_path / name).write_text("sample", encoding="utf-8")

    assert extract_title_from_document_name(names[0]) == "AI文明史·前史"
    assert extract_title_from_document_name(names[1]) == "AI工程 大模型应用开发实战"
    assert extract_title_from_document_name(names[2]) == "Claude Code Complete Guide"
    assert extract_title_from_document_name(names[3]) is None

    benchmark = title_benchmark_for_style("technical_deep_dive", source_dir=tmp_path)

    assert benchmark.sample_count == 3
    assert benchmark.soft_min >= 4
    assert benchmark.hard_max >= benchmark.soft_max
    assert "AI工程 大模型应用开发实战" in benchmark.examples


def test_workspace_finding_dto_exposes_title_benchmark_evidence():
    chapter_id = "chapter-id"
    issue = SimpleNamespace(
        id="finding-id",
        chapter_id=chapter_id,
        title="标题过长或营销化",
        explanation="标题过长。",
        quote="AI自动化写书终极秘籍",
        replacement_text="",
        issue_type="title_marketing_or_too_long",
        detector="title_reviewer",
        dimension="logic_structure",
        severity="medium",
        status="open",
        applied_at=None,
        resolved_at=None,
        char_start=None,
        char_end=None,
        paragraph_id=None,
        paragraph_index=1,
        quality_evidence={
            "product_dimension": "goal_alignment",
            "fix_capability": "choice_then_apply",
            "title_benchmark": {
                "source": "data/document",
                "sample_count": 20,
                "soft_min": 6,
                "soft_max": 27,
                "median_len": 16,
                "examples": ["AI工程 大模型应用开发实战", "从零构建大语言模型"],
            },
        },
    )
    chapter = SimpleNamespace(id=chapter_id, index=1, title="第一章")

    dto = ReviewWorkspaceService(SimpleNamespace())._chapter_issue_to_dto(  # type: ignore[arg-type]
        issue,
        {chapter_id: chapter},
        {},
    )

    evidence = dto["evidence_items"]
    assert evidence[0]["type"] == "title_benchmark"
    assert "20 个可识别标题" in evidence[0]["detail"]
    assert "6-27" in evidence[0]["detail"]
    assert "AI工程 大模型应用开发实战" in evidence[0]["examples"]
    assert dto["paragraph_index"] == 1


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
