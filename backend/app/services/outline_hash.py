"""大纲结构指纹，用于叙事宪法版本关联。"""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy.orm import Session

from app.models.chapter import Chapter


def compute_book_outline_hash(book_id: uuid.UUID, db: Session) -> str:
    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.index.asc())
        .all()
    )
    payload = []
    for ch in chapters:
        meta = ch.content if isinstance(ch.content, dict) else {}
        sections = meta.get("sections") or []
        sec_titles = [s.get("title", "") for s in sections if isinstance(s, dict)]
        payload.append(
            {
                "index": ch.index,
                "title": ch.title,
                "summary": (ch.summary or "")[:200],
                "key_points": list(meta.get("key_points") or [])[:20],
                "sections": sec_titles[:30],
            }
        )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
