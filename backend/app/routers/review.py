"""章节审校 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.review_agent import ReviewAgent
from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.chapters import _chat_model_for_book, _get_chapter
from app.models.figure import Figure
from app.schemas.review import (
    ChapterReviewIn,
    ChapterReviewOut,
    CitationLintIssueOut,
    ReviewApplyIssueIn,
    ReviewApplyIssueOut,
    ReviewIssueOut,
)
from app.services.review_apply import apply_review_issue_text
from app.services import book_service
from app.services.citation_lint import lint_chapter_citations
from app.services.citation_service import list_citations_sorted
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

    if body and body.text and body.text.strip():
        md = body.text.strip()
    else:
        content = ch.content if isinstance(ch.content, dict) else None
        md = chapter_content_to_markdown(content)

    if not md.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "本章暂无正文，请先写作或粘贴待审内容")

    citations = list_citations_sorted(db, book.id)
    cite_lines = [
        f"[{c.list_index or i}] {c.title} ({c.year or 'n.d.'})"
        for i, c in enumerate(citations, start=1)
    ][:200]
    figures = (
        db.query(Figure)
        .filter(Figure.book_id == book_id, Figure.chapter_index == chapter_index)
        .all()
    )
    figure_lines = [
        f"- {f.figure_type.value}: {(f.caption or f.raw_annotation or '')[:120]}"
        for f in figures
    ]

    agent = ReviewAgent(model=_chat_model_for_book(book))
    result = agent.review_chapter(
        chapter_title=ch.title or f"第{chapter_index}章",
        body=md,
        book_title=book.title or "",
        book_type=book.book_type.value,
        citation_style=book.citation_style.value if book.citation_style else "无",
        user_material=(book.user_material or ""),
        approved_citations=cite_lines,
        figure_summaries=figure_lines,
    )

    issues = [ReviewIssueOut.model_validate(x) for x in result.get("issues") or []]
    lint_raw = lint_chapter_citations(
        md,
        db,
        book.id,
        bracket_style=(book.citation_style and book.citation_style.value == "gb_t7714"),
    )
    citation_issues = [CitationLintIssueOut.model_validate(x.to_dict()) for x in lint_raw]
    return ChapterReviewOut(
        chapter_index=chapter_index,
        chapter_title=ch.title or "",
        summary=result.get("summary") or "",
        score=int(result.get("score") or 0),
        issues=issues,
        citation_issues=citation_issues,
        word_count=len(md),
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
    """按审校 action_type 生成可预览的修改结果（revise/insert 走 LLM）。"""
    book = book_service.get_book_or_404(book_id, user, db)
    _get_chapter(book_id, chapter_index, db)
    chat_model = _chat_model_for_book(book)
    try:
        result_text, preview_kind = apply_review_issue_text(
            book=book,
            chat_model=chat_model,
            action_type=body.action_type.value,
            quote=body.quote,
            suggestion=body.suggestion,
            detail=body.detail,
            context=body.context,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "AI 处理审校建议失败，请稍后重试",
        ) from e
    return ReviewApplyIssueOut(
        quote=body.quote,
        result_text=result_text,
        preview_kind=preview_kind,
    )
