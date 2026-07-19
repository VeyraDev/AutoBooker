"""共享书架 + 经典文献库 API。"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.database import get_db
from app.models.global_literature import GlobalLiterature
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.library import (
    AddShelfToBookIn,
    AddToBookIn,
    GlobalLiteratureListOut,
    GlobalLiteratureOut,
    LibraryCategoryOut,
    LibraryItemListOut,
    LibraryItemOut,
    LibraryItemUploadOut,
)
from app.services import book_service
from app.services.citation_service import create_citation_from_paper
from app.services.global_library_service import list_global_literature, seed_curated_library
from app.services import library_shelf_service as shelf

router = APIRouter(prefix="/library", tags=["library"])


def _item_out(row, *, user_id: UUID | None = None, categories_by_id: dict | None = None) -> LibraryItemOut:
    cat = None
    if categories_by_id and row.category_id:
        cat = categories_by_id.get(row.category_id)
    elif row.category is not None:
        cat = row.category
    return LibraryItemOut(
        id=str(row.id),
        title=row.title,
        authors=list(row.authors or []),
        description=row.description,
        category_id=str(row.category_id) if row.category_id else None,
        category_slug=getattr(cat, "slug", None) if cat else None,
        category_name=getattr(cat, "name", None) if cat else None,
        tags=list(row.tags or []),
        language=row.language,
        file_type=row.file_type,
        filename=row.filename,
        size_bytes=int(row.size_bytes or 0),
        uploader_name=row.uploader_name,
        use_count=int(row.use_count or 0),
        created_at=row.created_at.isoformat() if row.created_at else None,
        is_mine=bool(user_id and row.uploader_id == user_id),
    )


def _category_out(c) -> LibraryCategoryOut:
    return LibraryCategoryOut(
        id=str(c.id),
        slug=c.slug,
        name=c.name,
        description=c.description,
        sort_order=int(c.sort_order or 0),
    )


# ---------- 共享书架 ----------


@router.get("/shelf/categories", response_model=list[LibraryCategoryOut])
def list_shelf_categories(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [_category_out(c) for c in shelf.list_categories(db)]


@router.get("/shelf", response_model=LibraryItemListOut)
def list_shelf(
    category: str | None = Query(None, description="分类 slug"),
    q: str | None = Query(None),
    mine: bool = Query(False),
    limit: int = Query(48, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cats = shelf.list_categories(db)
    by_id = {c.id: c for c in cats}
    rows, total = shelf.list_shelf_items(
        db,
        category_slug=category,
        q=q,
        mine=mine,
        uploader_id=user.id if mine else None,
        limit=limit,
        offset=offset,
    )
    return LibraryItemListOut(
        items=[_item_out(r, user_id=user.id, categories_by_id=by_id) for r in rows],
        total=total,
        categories=[_category_out(c) for c in cats],
    )


@router.post("/shelf/upload", response_model=LibraryItemUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_shelf_item(
    file: UploadFile = File(...),
    title: str = Form(""),
    authors: str = Form("[]"),
    description: str = Form(""),
    category_slug: str = Form("other"),
    tags: str = Form("[]"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "缺少文件名")
    try:
        author_list = json.loads(authors) if authors else []
        if not isinstance(author_list, list):
            author_list = []
    except json.JSONDecodeError:
        author_list = [a.strip() for a in authors.split(",") if a.strip()]
    try:
        tag_list = json.loads(tags) if tags else []
        if not isinstance(tag_list, list):
            tag_list = []
    except json.JSONDecodeError:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    content = await file.read()
    item = shelf.create_shelf_item(
        db,
        user=user,
        title=title,
        authors=[str(a) for a in author_list],
        description=description,
        category_slug=category_slug or "other",
        tags=[str(t) for t in tag_list],
        filename=file.filename,
        content=content,
    )
    return LibraryItemUploadOut(item=_item_out(item, user_id=user.id))


@router.get("/shelf/{item_id}/content")
def download_shelf_item(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下载共享书架文件，供资料库 / 书稿上传复用。"""
    row = shelf.get_published_item(db, item_id)
    ascii_name = "".join(ch if 32 <= ord(ch) < 127 and ch not in '\\/"' else "_" for ch in (row.filename or "file"))
    cd = f"attachment; filename=\"{ascii_name or 'file'}\"; filename*=UTF-8''{quote(row.filename or 'file')}"
    return Response(
        content=bytes(row.content),
        media_type=row.mime_type or "application/octet-stream",
        headers={"Content-Disposition": cd},
    )


@router.get("/shelf/{item_id}", response_model=LibraryItemOut)
def get_shelf_item(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = shelf.get_published_item(db, item_id)
    return _item_out(row, user_id=user.id)


@router.post("/shelf/books/{book_id}/add")
def add_shelf_to_book(
    book_id: UUID,
    body: AddShelfToBookIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    item = shelf.get_published_item(db, UUID(body.item_id))
    ref = shelf.add_shelf_item_to_book(
        db,
        book=book,
        user=user,
        item=item,
        background_tasks=background_tasks,
    )
    return {"ok": True, "reference_file_id": str(ref.id), "book_id": str(book.id)}


# ---------- 经典文献（原 GlobalLiterature） ----------


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
