"""On-demand full-text source retrieval for startup assistant tools."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.book import Book
from app.services.sources.stage_source_context_service import StageSourceContextService


def retrieve_source_context(
    db: Session,
    book: Book,
    *,
    query: str,
    source_ids: list[str] | None = None,
    top_k: int = 12,
) -> dict[str, Any]:
    """Return relevant full-text chunks with stable source locators."""
    top_k = max(1, min(int(top_k or 12), 24))
    items = StageSourceContextService(db).retrieve(
        book.id,
        stage="assistant",
        query=query,
        source_ids=source_ids,
        top_k=top_k,
    )
    segments = [
        {
            "source_id": item.get("source_id"),
            "reference_file_id": item.get("reference_file_id"),
            "segment_id": item.get("chunk_id") or item.get("citation_id"),
            "segment_type": item.get("source_kind"),
            "title": item.get("title"),
            "location": item.get("locator") or "",
            "text": item.get("content") or "",
            "score": item.get("score") or 0.0,
            "directly_quotable": bool(item.get("directly_quotable")),
            "verification_status": item.get("verification_status"),
        }
        for item in items
    ]

    return {"query": query, "segments": segments, "count": len(segments)}
