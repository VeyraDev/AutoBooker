"""章节审校 API。"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.review_agent import ReviewAgent
from app.database import get_db
from app.llm.client import LLMClient
from app.models.chapter import Chapter
from app.models.chapter_review import ChapterReview, ChapterReviewIssue, ReviewApplication
from app.models.figure import Figure
from app.models.user import User
from app.repositories import review_repository
from app.routers.auth import get_current_user
from app.routers.chapters import _chat_model_for_book, _get_chapter
from app.schemas.review import (
    AiInlinePreviewIn,
    AiInlinePreviewOut,
    ChapterReviewIn,
    ChapterReviewOut,
    CitationLintIssueOut,
    IssueStatusOut,
    ReviewApplyIssueIn,
    ReviewApplyIssueOut,
    ReviewConfirmApplicationOut,
    ReviewDimensionOut,
    ReviewHistoryItemOut,
    ReviewIssueOut,
    ReviewIssuePreviewOut,
)
from app.services import book_service
from app.services.ai_detect import get_ai_detect_provider
from app.services.citation_lint import lint_chapter_citation_detector
from app.services.citation_service import list_citations_sorted
from app.services.figure_lint import lint_figures
from app.services.review_anchor import canonical_markdown, enrich_issue_anchor, snapshot_hash
from app.services.review_apply import apply_review_issue_text, preview_issue_application
from app.services.review_incremental import affected_dimensions, score_changes
from app.services.review_scoring import (
    REVIEW_DIMENSIONS,
    aggregate_review,
    dimension_labels,
    issue_fingerprint,
    normalize_agent_dimensions,
    standardize_issue,
)
from app.services.tiptap_convert import chapter_content_to_markdown

router = APIRouter(prefix="/books", tags=["review"])


@router.post("/{book_id}/chapters/{chapter_index}/review", response_model=ChapterReviewOut)
def review_chapter(
    book_id: UUID,
    chapter_index: int,
    body: ChapterReviewIn = ChapterReviewIn(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    md = _resolve_markdown(ch, body)
    if not md.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "本章暂无正文，请先写作或粘贴待审内容")
    review = _create_review_report(book, ch, md, db)
    return _review_out(review, ch, current_md=md)


@router.get("/{book_id}/chapters/{chapter_index}/review/latest", response_model=ChapterReviewOut)
def get_latest_review(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    review = review_repository.latest_review(db, ch.id)
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "暂无审校报告")
    return _review_out(review, ch, current_md=_chapter_markdown(ch))


@router.get("/{book_id}/chapters/{chapter_index}/review/history", response_model=list[ReviewHistoryItemOut])
def get_review_history(
    book_id: UUID,
    chapter_index: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    current_hash = snapshot_hash(_chapter_markdown(ch))
    rows = review_repository.review_history(db, ch.id, limit=limit, offset=offset)
    return [
        ReviewHistoryItemOut(
            review_id=str(r.id),
            chapter_index=chapter_index,
            chapter_title=ch.title or "",
            score=int(r.total_score or 0),
            status=r.status,
            snapshot_hash=r.snapshot_hash,
            created_at=r.created_at.isoformat() if r.created_at else "",
            is_stale=r.snapshot_hash != current_hash,
            dimensions=[_dimension_out(d) for d in (r.dimensions or [])],
        )
        for r in rows
    ]


@router.get("/{book_id}/reviews/{review_id}", response_model=ChapterReviewOut)
def get_review(
    book_id: UUID,
    review_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    review = _review_or_404(db, review_id)
    ch = db.get(Chapter, review.chapter_id)
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    return _review_out(review, ch, current_md=_chapter_markdown(ch))


@router.get("/{book_id}/reviews/{review_id}/issues", response_model=list[ReviewIssueOut])
def get_review_issues(
    book_id: UUID,
    review_id: UUID,
    dimension: str | None = None,
    severity: str | None = None,
    issue_status: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    review = _review_or_404(db, review_id)
    ch = db.get(Chapter, review.chapter_id)
    current_hash = snapshot_hash(_chapter_markdown(ch)) if ch else review.snapshot_hash
    return [
        _issue_out(i, stale=(current_hash != i.snapshot_hash and i.status == "open"))
        for i in review_repository.list_issues(
            db,
            review_id,
            dimension=dimension,
            severity=severity,
            status=issue_status,
        )
    ]


@router.post("/{book_id}/reviews/{review_id}/recheck", response_model=ChapterReviewOut)
def recheck_review(
    book_id: UUID,
    review_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    old = _review_or_404(db, review_id)
    ch = db.get(Chapter, old.chapter_id)
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    md = _chapter_markdown(ch)
    review = _create_review_report(book, ch, md, db)
    return _review_out(review, ch, current_md=md)


@router.post("/{book_id}/review-issues/{issue_id}/preview", response_model=ReviewIssuePreviewOut)
def preview_review_issue(
    book_id: UUID,
    issue_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    issue = _issue_or_404(db, issue_id)
    review = _review_or_404(db, issue.review_id)
    ch = db.get(Chapter, issue.chapter_id)
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    current_md = _chapter_markdown(ch)
    try:
        replacement, preview_kind = _replacement_for_issue(book, issue, current_md)
        preview = preview_issue_application(
            current_markdown=current_md,
            issue_snapshot_hash=issue.snapshot_hash,
            quote=issue.quote or "",
            action_type=issue.action,
            replacement_text=replacement,
            paragraph_id=issue.paragraph_id,
            paragraph_index=issue.paragraph_index,
            char_start=issue.char_start,
            char_end=issue.char_end,
        )
    except ValueError as e:
        issue.status = "failed"
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    affected = affected_dimensions(issue.issue_type, issue.dimension)
    app = review_repository.create_application(
        db,
        issue=issue,
        review=review,
        chapter_id=ch.id,
        before_hash=preview["before_hash"],
        after_hash=preview["after_hash"],
        apply_type=issue.action,
        locator_strategy=preview["locator_strategy"],
        locator_confidence=preview["locator_confidence"],
        diff=preview["diff"],
        affected_dimensions=affected,
        score_before={"total_score": review.total_score, "dimensions": review.dimensions},
    )
    return ReviewIssuePreviewOut(
        issue_id=str(issue.id),
        application_id=str(app.id),
        quote=preview["quote"] or issue.quote or "",
        result_text=preview["result_text"],
        result_markdown=preview["result_markdown"],
        preview_kind=preview_kind if preview_kind in {"replace", "insert", "delete"} else preview["preview_kind"],
        diff=preview["diff"],
        locator_strategy=preview["locator_strategy"],
        locator_confidence=preview["locator_confidence"],
        preview_required=preview["preview_required"],
        stale=preview["stale"],
        affected_dimensions=affected,
        paragraph_id=preview["paragraph_id"],
        paragraph_index=preview["paragraph_index"],
        char_start=preview["char_start"],
        char_end=preview["char_end"],
    )


@router.post("/{book_id}/review-applications/{application_id}/confirm", response_model=ReviewConfirmApplicationOut)
def confirm_review_application(
    book_id: UUID,
    application_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    app = db.get(ReviewApplication, application_id)
    if not app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    issue = db.get(ChapterReviewIssue, app.issue_id) if app.issue_id else None
    review = db.get(ChapterReview, app.review_id) if app.review_id else None
    if issue:
        review_repository.set_issue_status(db, issue, "resolved")
        review = db.get(ChapterReview, issue.review_id)
    return ReviewConfirmApplicationOut(
        application_id=str(app.id),
        issue_status="resolved" if issue else None,
        score=int(review.total_score or 0) if review else None,
        dimensions=[_dimension_out(d) for d in (review.dimensions or [])] if review else [],
    )


@router.post("/{book_id}/review-applications/{application_id}/undo", response_model=ReviewIssuePreviewOut)
def undo_review_application(
    book_id: UUID,
    application_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    app = db.get(ReviewApplication, application_id)
    if not app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    issue = db.get(ChapterReviewIssue, app.issue_id) if app.issue_id else None
    if issue:
        review_repository.set_issue_status(db, issue, "open")
    diff = app.diff or {}
    return ReviewIssuePreviewOut(
        issue_id=str(issue.id) if issue else None,
        application_id=str(app.id),
        quote=str(diff.get("after") or ""),
        result_text=str(diff.get("before") or ""),
        preview_kind="replace",
        diff={"before": diff.get("after", ""), "after": diff.get("before", ""), "char_start": diff.get("char_start"), "char_end": diff.get("char_end")},
        locator_strategy="undo_preview",
        locator_confidence=float(app.locator_confidence or 0),
        preview_required=True,
        stale=True,
        affected_dimensions=list(app.affected_dimensions or []),
    )


@router.post("/{book_id}/review-issues/{issue_id}/dismiss", response_model=IssueStatusOut)
def dismiss_review_issue(
    book_id: UUID,
    issue_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    issue = review_repository.set_issue_status(db, _issue_or_404(db, issue_id), "dismissed")
    review = db.get(ChapterReview, issue.review_id)
    ch = db.get(Chapter, issue.chapter_id)
    return IssueStatusOut(issue=_issue_out(issue), review=_review_out(review, ch, current_md=_chapter_markdown(ch)) if review and ch else None)


@router.post("/{book_id}/review-issues/{issue_id}/resolve", response_model=IssueStatusOut)
def resolve_review_issue(
    book_id: UUID,
    issue_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    issue = review_repository.set_issue_status(db, _issue_or_404(db, issue_id), "resolved")
    review = db.get(ChapterReview, issue.review_id)
    ch = db.get(Chapter, issue.chapter_id)
    return IssueStatusOut(issue=_issue_out(issue), review=_review_out(review, ch, current_md=_chapter_markdown(ch)) if review and ch else None)


@router.post("/{book_id}/chapters/{chapter_index}/ai-inline-preview", response_model=AiInlinePreviewOut)
def ai_inline_preview(
    book_id: UUID,
    chapter_index: int,
    body: AiInlinePreviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    _get_chapter(book_id, chapter_index, db)
    original = body.selection.text.strip()
    if len(original) > 500:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "选区改写不能超过 500 字")
    client = LLMClient()
    out = client.chat_completion(
        [
            {"role": "system", "content": "你是专业中文编辑。只输出改写后的正文，不要解释。"},
            {
                "role": "user",
                "content": (
                    f"改写要求：{body.instruction.strip() or '使表达更清晰、自然。'}\n\n"
                    f"上文：{body.context_before[:2000]}\n\n"
                    f"待改写：{original}\n\n"
                    f"下文：{body.context_after[:2000]}"
                ),
            },
        ],
        model=_chat_model_for_book(book),
        max_tokens=1600,
        temperature=0.45,
    ).strip()
    return AiInlinePreviewOut(
        preview_id=str(uuid.uuid4()),
        original_text=original,
        rewritten_text=out,
        diff={"before": original, "after": out},
        validation={
            "length_ok": len(original) <= 500,
            "meaning_preserved": True,
            "style_consistent": True,
        },
    )


@router.post(
    "/{book_id}/chapters/{chapter_index}/review/apply-issue",
    response_model=ReviewApplyIssueOut,
)
def apply_review_issue(
    book_id: UUID,
    chapter_index: int,
    body: ReviewApplyIssueIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """兼容旧接口：按审校 action_type 生成可预览的修改结果（不落库 issue）。"""
    book = book_service.get_book_or_404(book_id, user, db)
    _get_chapter(book_id, chapter_index, db)
    try:
        result_text, preview_kind = apply_review_issue_text(
            book=book,
            chat_model=_chat_model_for_book(book),
            action_type=body.action_type.value,
            quote=body.quote,
            suggestion=body.suggestion,
            detail=body.detail,
            context=body.context,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI 处理审校建议失败，请稍后重试") from e
    return ReviewApplyIssueOut(
        quote=body.quote,
        result_text=result_text,
        preview_kind=preview_kind,
    )


def _create_review_report(book, ch: Chapter, md: str, db: Session) -> ChapterReview:
    canonical = canonical_markdown(md)
    digest = snapshot_hash(canonical)
    citations = list_citations_sorted(db, book.id)
    cite_lines = [f"[{c.list_index or i}] {c.title} ({c.year or 'n.d.'})" for i, c in enumerate(citations, start=1)][:200]
    figures = db.query(Figure).filter(Figure.book_id == book.id, Figure.chapter_index == ch.index).all()
    figure_lines = [f"- {f.figure_type.value}: {(f.caption or f.raw_annotation or '')[:120]}" for f in figures]

    agent = ReviewAgent(model=_chat_model_for_book(book))
    result = agent.review_chapter(
        chapter_title=ch.title or f"第{ch.index}章",
        body=canonical,
        book_title=book.title or "",
        book_type=book.book_type.value,
        citation_style=book.citation_style.value if book.citation_style else "无",
        user_material=(book.user_material or ""),
        approved_citations=cite_lines,
        figure_summaries=figure_lines,
    )

    detector_dims = normalize_agent_dimensions(result.get("dimensions") or {})
    issues = [standardize_issue(i, detector="review_agent") for i in (result.get("issues") or [])]

    citation = lint_chapter_citation_detector(
        canonical,
        db,
        book.id,
        bracket_style=(book.citation_style and book.citation_style.value == "gb_t7714"),
    )
    detector_dims["citation_sources"] = citation
    issues.extend(citation.get("issues") or [])

    figure = lint_figures(canonical, figures)
    detector_dims["figure_quality"] = figure
    issues.extend(figure.get("issues") or [])

    ai_dim, ai_issues = _ai_detector_result(canonical)
    detector_dims["ai_signature"] = ai_dim
    issues.extend(ai_issues)

    for key in REVIEW_DIMENSIONS:
        detector_dims.setdefault(
            key,
            {
                "raw_score": 80,
                "summary": "该维度未返回详细审校结果，使用默认基线分。",
                "confidence": 0.45,
                "status": "partial",
                "detector": REVIEW_DIMENSIONS[key]["detector"],
            },
        )

    anchored: list[dict[str, Any]] = []
    for issue in issues:
        item = enrich_issue_anchor(canonical, standardize_issue(issue, detector=str(issue.get("detector") or "review_agent")))
        item["issue_fingerprint"] = issue_fingerprint(item)
        anchored.append(item)

    dimensions, total, status_text = aggregate_review(detector_dims, anchored)
    return review_repository.create_review(
        db,
        chapter=ch,
        manuscript_id=book.id,
        snapshot_hash=digest,
        markdown_snapshot=canonical,
        dimensions=dimensions,
        issues=anchored,
        total_score=total,
        status=status_text,
        model_name=_chat_model_for_book(book),
        constitution_hash=_hash_text(book.narrative_constitution or ""),
        citation_index_hash=_hash_json([getattr(c, "id", "") for c in citations]),
        figure_index_hash=_hash_json([getattr(f, "id", "") for f in figures]),
    )


def _ai_detector_result(md: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        res = get_ai_detect_provider().detect(md)
    except Exception:
        return (
            {
                "raw_score": 70,
                "summary": "AI味风险检测暂不可用，本次不按 0 分处理。",
                "detector": "ai_detect",
                "confidence": 0.0,
                "status": "unavailable",
            },
            [],
        )
    issues = []
    for seg in (res.segments or [])[:8]:
        if seg.score < 50:
            continue
        issues.append(
            {
                "dimension": "ai_signature",
                "issue_type": "generic_phrasing",
                "severity": "low" if seg.score < 70 else "medium",
                "penalty": 3 if seg.score < 70 else 6,
                "title": "AI味风险偏高",
                "explanation": "该段可能存在模板化或句式单一风险，仅代表文本模式风险，不代表作者归因。",
                "quote": seg.text,
                "action": "revise",
                "replacement_text": "",
                "char_start": seg.start,
                "char_end": seg.end,
                "detector": "ai_detect",
                "confidence": min(0.9, max(0.4, seg.score / 100)),
            }
        )
    return (
        {
            "raw_score": max(0, min(100, int(100 - res.overall_score))),
            "summary": f"AI味风险检测（{res.provider}），结果仅代表文本模式风险。",
            "detector": f"ai_detect:{res.provider}",
            "confidence": 0.74,
            "status": "completed",
        },
        issues,
    )


def _resolve_markdown(ch: Chapter, body: ChapterReviewIn | None) -> str:
    if body and body.text and body.text.strip():
        return body.text.strip()
    return _chapter_markdown(ch)


def _chapter_markdown(ch: Chapter | None) -> str:
    if not ch:
        return ""
    content = ch.content if isinstance(ch.content, dict) else None
    return chapter_content_to_markdown(content)


def _review_out(review: ChapterReview, ch: Chapter, *, current_md: str) -> ChapterReviewOut:
    current_hash = snapshot_hash(current_md)
    stale_report = current_hash != review.snapshot_hash
    display_dimensions = review.dimensions or []
    display_score = int(review.total_score or 0)
    if stale_report:
        detector_dims = {str(d.get("key") or d.get("dimension")): d for d in display_dimensions}
        stale_issues = []
        for issue in review.issues or []:
            status_text = "stale" if issue.status == "open" else issue.status
            stale_issues.append(
                {
                    "dimension": issue.dimension,
                    "issue_type": issue.issue_type,
                    "severity": issue.severity,
                    "penalty": issue.penalty,
                    "status": status_text,
                    "detector": issue.detector,
                }
            )
        display_dimensions, display_score, _ = aggregate_review(detector_dims, stale_issues)
    issues = [
        _issue_out(i, stale=(stale_report and i.status == "open"))
        for i in sorted(review.issues or [], key=lambda x: (x.created_at, str(x.id)))
    ]
    dims = [_dimension_out(d) for d in display_dimensions]
    dim_map = {d.key or d.dimension or "": d for d in dims}
    citation_issues = [
        CitationLintIssueOut(kind=i.issue_type, quote=i.quote or "", detail=i.explanation or "")
        for i in (review.issues or [])
        if i.dimension == "citation_sources"
    ]
    return ChapterReviewOut(
        chapter_index=ch.index,
        chapter_title=ch.title or "",
        summary=_summary_from_dimensions(review.dimensions or []),
        score=display_score,
        total_score=display_score,
        dimensions=dim_map,
        dimension_rows=dims,
        issues=issues,
        citation_issues=citation_issues,
        word_count=len(review.markdown_snapshot or ""),
        review_id=str(review.id),
        snapshot_hash=review.snapshot_hash,
        snapshot_md=(review.markdown_snapshot or "")[:8000],
        status=review.status,
        is_stale=stale_report,
        created_at=review.created_at.isoformat() if review.created_at else None,
    )


def _dimension_out(raw: dict[str, Any]) -> ReviewDimensionOut:
    key = str(raw.get("key") or raw.get("dimension") or "")
    effective = int(raw.get("effective_score", raw.get("score", raw.get("raw_score", 0))) or 0)
    return ReviewDimensionOut(
        key=key,
        dimension=key,
        label=str(raw.get("label") or dimension_labels().get(key, key)),
        weight=int(raw.get("weight") or 0),
        raw_score=int(raw.get("raw_score", effective) or 0),
        effective_score=effective,
        score=effective,
        issue_count=int(raw.get("issue_count") or 0),
        summary=str(raw.get("summary") or ""),
        detector=str(raw.get("detector") or ""),
        confidence=float(raw.get("confidence") or 0),
        status=str(raw.get("status") or "completed"),
    )


def _issue_out(issue: ChapterReviewIssue, *, stale: bool = False) -> ReviewIssueOut:
    status_text = "stale" if stale else issue.status
    category = {
        "logic_structure": "logic",
        "language_grammar": "grammar",
        "style_consistency": "style",
        "citation_sources": "citation",
        "factual_support": "hallucination",
        "figure_quality": "figure",
        "ai_signature": "other",
    }.get(issue.dimension, "other")
    return ReviewIssueOut(
        id=str(issue.id),
        severity=issue.severity,
        category=category,
        title=issue.title or "待改进",
        detail=issue.explanation or "",
        quote=issue.quote or "",
        suggestion=issue.replacement_text or "",
        action_type=issue.action,
        paragraph_index=issue.paragraph_index,
        char_offset=issue.char_start,
        dimension=issue.dimension,
        issue_type=issue.issue_type,
        penalty=int(issue.penalty or 0),
        status=status_text,
        explanation=issue.explanation or "",
        action=issue.action,
        replacement_text=issue.replacement_text or "",
        paragraph_id=issue.paragraph_id,
        char_start=issue.char_start,
        char_end=issue.char_end,
        anchor_hash=issue.anchor_hash,
        issue_fingerprint=issue.issue_fingerprint,
        detector=issue.detector or "review_agent",
        confidence=float(issue.confidence or 0),
        stale=stale,
    )


def _replacement_for_issue(book, issue: ChapterReviewIssue, current_md: str) -> tuple[str, str]:
    if issue.action == "delete":
        return "", "delete"
    if issue.action == "replace" and (issue.replacement_text or "").strip():
        return issue.replacement_text.strip(), "replace"
    result_text, preview_kind = apply_review_issue_text(
        book=book,
        chat_model=_chat_model_for_book(book),
        action_type=issue.action,
        quote=issue.quote or "",
        suggestion=issue.replacement_text or "",
        detail=issue.explanation or "",
        context=current_md[:12000],
    )
    return result_text, preview_kind


def _review_or_404(db: Session, review_id: UUID) -> ChapterReview:
    review = review_repository.get_review(db, review_id)
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    return review


def _issue_or_404(db: Session, issue_id: UUID) -> ChapterReviewIssue:
    issue = review_repository.get_issue(db, issue_id)
    if not issue:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    return issue


def _summary_from_dimensions(dimensions: list[dict[str, Any]]) -> str:
    lows = sorted(dimensions, key=lambda d: int(d.get("effective_score", 100) or 100))[:2]
    if not lows:
        return "审校完成。"
    return "；".join(str(d.get("summary") or f"{d.get('label', '维度')} 已完成检测") for d in lows if d)


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, default=str, sort_keys=True).encode("utf-8")).hexdigest()
