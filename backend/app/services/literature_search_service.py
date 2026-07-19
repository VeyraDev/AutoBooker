"""Literature search service extracted from router for tool orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.literature_agent import (
    LiteratureAgent,
    _preserve_english_raw_query,
    _should_skip_auto_refine,
)
from app.models.book import Book
from app.services.literature_profiles import literature_profile, profile_source_hint
from app.services.literature_query_refiner import refine_literature_query


def _to_paper_dicts(raw: list) -> list[dict]:
    out: list[dict] = []
    for item in raw:
        if hasattr(item, "model_dump"):
            out.append(item.model_dump())
        elif isinstance(item, dict):
            out.append(item)
    return out


class LiteratureSearchService:
    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        book: Book,
        *,
        query: str,
        chapter_index: int | None = None,
        rows: int = 8,
        skip_refine: bool = False,
    ) -> dict:
        profile = literature_profile(book.book_type, book.style_type)
        agent = LiteratureAgent()
        raw_q = query.strip()
        must_inc: list[str] = []
        must_exc: list[str] = []

        if _should_skip_auto_refine(raw_q):
            queries = [raw_q]
        else:
            refined = refine_literature_query(
                self.db,
                book,
                raw_query=raw_q,
                chapter_index=chapter_index,
            )
            queries = refined["refined_queries"]
            must_inc = refined.get("must_include") or []
            must_exc = refined.get("must_exclude") or []
            if skip_refine and raw_q:
                queries = [raw_q]

        if not queries:
            queries = [raw_q] if raw_q else []
        queries = _preserve_english_raw_query(raw_q, queries)
        if not queries:
            raise ValueError("请提供检索词")

        tabbed = agent.search_tabbed(
            queries,
            profile,
            rows=rows,
            must_include=must_inc,
            must_exclude=must_exc,
            raw_query=raw_q,
        )
        papers = _to_paper_dicts(tabbed["papers"])
        github = _to_paper_dicts(tabbed["github"])
        wiki = _to_paper_dicts(tabbed["wiki"])
        official = _to_paper_dicts(tabbed["official_docs"])
        flat = papers + github + wiki + official

        book.last_literature_query = {
            "query": raw_q,
            "refined_queries": tabbed.get("refined_queries") or queries,
            "must_include": must_inc,
            "must_exclude": must_exc,
            "chapter_index": chapter_index,
        }
        self.db.flush()

        return {
            "query": raw_q,
            "chapter_index": chapter_index,
            "papers": papers,
            "github": github,
            "wiki": wiki,
            "official_docs": official,
            "items": flat,
            "refined_queries": tabbed.get("refined_queries") or queries,
            "warnings": tabbed.get("warnings") or [],
            "profile": profile,
            "source_hint": profile_source_hint(profile),
        }
