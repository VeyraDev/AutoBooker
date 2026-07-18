"""On-demand source segment retrieval for startup assistant tools."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.source_segment import SourceSegment
from app.services.sources.source_library_service import SourceLibraryService


def _tokenize(query: str) -> list[str]:
    raw = (query or "").strip().lower()
    if not raw:
        return []
    parts = re.split(r"[\s,，、;；|/]+", raw)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if len(p) >= 2 and p not in out:
            out.append(p)
        if len(out) >= 16:
            break
    if not out and raw:
        out = [raw[:40]]
    return out


def _score_text(text: str, tokens: list[str]) -> float:
    hay = (text or "").lower()
    if not hay or not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in hay)
    return hits / max(len(tokens), 1)


def retrieve_source_context(
    db: Session,
    book: Book,
    *,
    query: str,
    source_ids: list[str] | None = None,
    top_k: int = 12,
) -> dict[str, Any]:
    """Return relevant text segments for the current question (not web search)."""
    tokens = _tokenize(query)
    top_k = max(1, min(int(top_k or 12), 24))
    allowed: set[UUID] | None = None
    if source_ids:
        allowed = set()
        for sid in source_ids:
            try:
                allowed.add(UUID(str(sid)))
            except (TypeError, ValueError):
                continue

    segs = (
        db.query(SourceSegment)
        .filter(SourceSegment.book_id == book.id)
        .order_by(SourceSegment.created_at.desc())
        .limit(200)
        .all()
    )
    scored: list[tuple[float, SourceSegment]] = []
    for seg in segs:
        if allowed is not None and seg.source_id not in allowed and seg.id not in allowed:
            continue
        blob = "\n".join(
            x for x in [seg.summary or "", seg.excerpt or "", seg.suggested_usage or ""] if x
        )
        score = _score_text(blob, tokens)
        if score <= 0 and tokens:
            # Keep a weak fallback when filtering by source_ids
            if allowed is not None:
                score = 0.05
            else:
                continue
        scored.append((score, seg))

    scored.sort(key=lambda x: x[0], reverse=True)
    segments: list[dict[str, Any]] = []
    for score, seg in scored[:top_k]:
        text = (seg.excerpt or seg.summary or "").strip()
        if not text:
            continue
        segments.append(
            {
                "source_id": str(seg.source_id),
                "segment_id": str(seg.id),
                "segment_type": seg.segment_type.value if seg.segment_type else "",
                "location": seg.locator or "",
                "text": text[:2000],
                "score": round(score, 3),
            }
        )

    # Fallback: if no segments, pull intake preview for named sources
    if not segments and allowed:
        lib = SourceLibraryService(db)
        for sid in list(allowed)[:5]:
            item = lib.get_item(book.id, sid)
            if not item:
                continue
            preview = (item.parsed_preview or item.text_content or "").strip()
            if not preview:
                continue
            segments.append(
                {
                    "source_id": str(item.id),
                    "segment_id": None,
                    "segment_type": "preview",
                    "location": "parsed_preview",
                    "text": preview[:2000],
                    "score": 0.1,
                }
            )

    return {"query": query, "segments": segments, "count": len(segments)}
