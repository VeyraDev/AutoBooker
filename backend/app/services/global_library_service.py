"""公共经典文献库服务。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.global_literature import (
    GlobalLiterature,
    GlobalLiteratureSource,
    GlobalLiteratureStatus,
)

_CLASSIC_PATH = Path(__file__).resolve().parent.parent / "data" / "classic_papers.json"


def seed_curated_library(db: Session) -> int:
    if not _CLASSIC_PATH.is_file():
        return 0
    existing = db.query(GlobalLiterature).filter(GlobalLiterature.source == GlobalLiteratureSource.curated).count()
    if existing > 0:
        return 0
    raw = json.loads(_CLASSIC_PATH.read_text(encoding="utf-8"))
    papers: list[dict] = []
    if isinstance(raw, list):
        papers = raw
    elif isinstance(raw, dict):
        concepts = raw.get("concepts") or {}
        if isinstance(concepts, dict):
            seen: set[str] = set()
            for _tag, items in concepts.items():
                if not isinstance(items, list):
                    continue
                for p in items:
                    if isinstance(p, dict):
                        key = p.get("doi") or p.get("title") or ""
                        if key and key not in seen:
                            seen.add(key)
                            papers.append({**p, "tags": [*_tag] if isinstance(_tag, str) else []})
        papers.extend(raw.get("papers") or [])
    count = 0
    for p in papers:
        if not isinstance(p, dict):
            continue
        row = GlobalLiterature(
            source=GlobalLiteratureSource.curated,
            status=GlobalLiteratureStatus.approved,
            title=str(p.get("title") or "")[:500],
            authors=p.get("authors") or [],
            year=p.get("year"),
            journal=p.get("journal") or p.get("venue") or "",
            doi=p.get("doi") or "",
            url=p.get("url") or "",
            abstract=(p.get("abstract") or "")[:4000],
            tags=p.get("tags") or p.get("concepts") or [],
        )
        db.add(row)
        count += 1
    db.commit()
    return count


def list_global_literature(
    db: Session,
    *,
    source: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    contributor_id: UUID | None = None,
) -> list[GlobalLiterature]:
    qry = db.query(GlobalLiterature).filter(GlobalLiterature.status == GlobalLiteratureStatus.approved)
    if source:
        qry = qry.filter(GlobalLiterature.source == source)
    if contributor_id:
        qry = qry.filter(GlobalLiterature.contributor_id == contributor_id)
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(GlobalLiterature.title.ilike(like))
    rows = qry.order_by(GlobalLiterature.cite_count.desc(), GlobalLiterature.created_at.desc()).offset(offset).limit(limit).all()
    if tag:
        rows = [r for r in rows if tag in (r.tags or [])]
    return rows
