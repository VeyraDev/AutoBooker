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
from app.schemas.review import ChapterReviewIn, ChapterReviewOut, ReviewIssueOut
from app.services import book_service
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

    agent = ReviewAgent(model=_chat_model_for_book(book))
    result = agent.review_chapter(
        chapter_title=ch.title or f"第{chapter_index}章",
        body=md,
        book_title=book.title or "",
        book_type=book.book_type.value,
        citation_style=book.citation_style.value if book.citation_style else "无",
        user_material=(book.user_material or ""),
    )

    issues = [ReviewIssueOut.model_validate(x) for x in result.get("issues") or []]
    return ChapterReviewOut(
        chapter_index=chapter_index,
        chapter_title=ch.title or "",
        summary=result.get("summary") or "",
        score=int(result.get("score") or 0),
        issues=issues,
        word_count=len(md),
    )
