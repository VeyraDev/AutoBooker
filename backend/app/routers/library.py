"""公共经典文献库 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.global_literature import GlobalLiterature, GlobalLiteratureSource
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.library import AddToBookIn, GlobalLiteratureListOut, GlobalLiteratureOut
from app.services import book_service
from app.services.citation_service import create_citation_from_paper
from app.services.global_library_service import list_global_literature, seed_curated_library

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=GlobalLiteratureListOut)
def list_library(
    source: str | None = Query(None),
    tag: str | None = Query(None),
    q: str | None = Query(None),
    mine: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seed_curated_library(db)
    rows = list_global_literature(
        db,
        source=source,
        tag=tag,
        q=q,
        contributor_id=user.id if mine else None,
    )
    items = [
        GlobalLiteratureOut(
            id=str(r.id),
            source=r.source.value,
            title=r.title,
            authors=list(r.authors or []),
            year=r.year,
            journal=r.journal,
            doi=r.doi,
            url=r.url,
            abstract=r.abstract,
            tags=list(r.tags or []),
            contributor_name=r.contributor_name,
            cite_count=r.cite_count or 0,
        )
        for r in rows
    ]
    return GlobalLiteratureListOut(items=items, total=len(items))


@router.post("/books/{book_id}/add")
def add_library_to_book(
    book_id: UUID,
    body: AddToBookIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    row = db.get(GlobalLiterature, UUID(body.literature_id))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文献不存在")
    payload = {
        "title": row.title,
        "authors": row.authors or [],
        "year": row.year,
        "journal": row.journal,
        "doi": row.doi,
        "url": row.url,
        "source": "literature_search",
        "external_source": f"library:{row.source.value}",
        "quotable_snippet": (row.abstract or "")[:600],
    }
    cite = create_citation_from_paper(db, book, payload)
    row.cite_count = (row.cite_count or 0) + 1
    db.commit()
    return {"ok": True, "citation_id": str(cite.id)}
