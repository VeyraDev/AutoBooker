"""Compatibility wrapper over the unified source-search service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.book import Book
from app.schemas.source_search import SourceSearchIn
from app.services.source_search.service import UnifiedSourceSearchService


class LiteratureSearchService:
    def __init__(self, db: Session):
        self.db = db
        self._search = UnifiedSourceSearchService()

    def search(
        self,
        book: Book,
        *,
        query: str | None = None,
        queries: list[str] | None = None,
        chapter_index: int | None = None,
        rows: int = 8,
        skip_refine: bool = False,
    ) -> dict:
        del skip_refine
        prepared = [str(value).strip() for value in (queries or []) if str(value).strip()]
        raw_query = (query or (prepared[0] if prepared else "")).strip()
        if not raw_query:
            raise ValueError("请提供检索词")
        scope = "chapter" if chapter_index is not None else "book"
        result = self._search.search(
            SourceSearchIn(
                query=raw_query,
                rows=rows,
                scope=scope,
                chapter_index=chapter_index,
                requested_source_types=["paper", "technical", "web"],
            ),
            book=book,
        )
        book.last_literature_query = {
            "query": raw_query,
            "intent": result.plan.intent.model_dump(),
            "execution": result.execution.model_dump(),
            "chapter_index": chapter_index,
        }
        self.db.flush()
        return result.model_dump(mode="json")
