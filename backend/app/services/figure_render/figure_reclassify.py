"""兼容 shim → figures.pipeline.orchestrator"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.llm.providers import resolve_book_ai_model
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.figure import Figure
from app.services.figure_service import _LEGACY_TAG_BY_TYPE
from app.services.figures.pipeline.orchestrator import classify_and_persist


def refresh_figure_classification(
    fig: Figure,
    book: Book,
    db: Session,
    *,
    chapter_title: str = "",
    user_hint: str = "",
    use_llm: bool = True,
) -> Figure:
    if not chapter_title:
        ch = db.query(Chapter).filter_by(book_id=book.id, index=fig.chapter_index).first()
        chapter_title = ch.title if ch else ""
    legacy = _LEGACY_TAG_BY_TYPE.get(fig.figure_type)
    return classify_and_persist(
        fig,
        db,
        style_type=book.style_type,
        book_type=book.book_type.value if book.book_type else "",
        chapter_title=chapter_title,
        legacy_tag=legacy,
        user_hint=user_hint,
        model=resolve_book_ai_model(book),
        use_llm=use_llm,
    )
