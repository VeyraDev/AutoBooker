"""Source library API (intake items unified view)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reference import ParseStatus, ReferenceFile
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.project_assistant import ConfirmSegmentIn, PasteSourceIn, SourceOut, SourceSegmentOut
from app.schemas.source_search import (
    SourceCapabilityOut,
    SourceSearchIn,
    SourceSearchOut,
    SourceSearchPlanIn,
    SourceSearchPlanOut,
    SourceSearchResultAddIn,
    SourceSearchResultAddOut,
)
from app.services import book_service
from app.services.citation_service import create_citation_from_paper
from app.models.citation import CitationSource
from app.schemas.citation import CitationOut
from app.services.source_search.connectors import citation_metadata
from app.services.source_search.service import UnifiedSourceSearchService
from app.services.sources.source_library_service import SourceLibraryService
from app.services.sources.source_segment_service import SourceSegmentService

router = APIRouter(prefix="/books", tags=["sources"])


@router.get("/{book_id}/sources/search-capabilities", response_model=list[SourceCapabilityOut])
def source_search_capabilities(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    return [SourceCapabilityOut.model_validate(row) for row in UnifiedSourceSearchService().capabilities()]


@router.post("/{book_id}/sources/search-plan", response_model=SourceSearchPlanOut)
def source_search_plan(
    book_id: UUID,
    body: SourceSearchPlanIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    return UnifiedSourceSearchService().plan(body, book=book)


@router.post("/{book_id}/sources/search", response_model=SourceSearchOut)
def source_search(
    book_id: UUID,
    body: SourceSearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    result = UnifiedSourceSearchService().search(body, book=book)
    book.last_literature_query = {
        "query": result.query,
        "intent": result.plan.intent.model_dump(),
        "requested_source_types": result.plan.requested_source_types,
        "execution": result.execution.model_dump(),
    }
    db.commit()
    return result


@router.post("/{book_id}/sources/search-results/add", response_model=SourceSearchResultAddOut)
def add_source_search_results(
    book_id: UUID,
    body: SourceSearchResultAddIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    source_service = SourceLibraryService(db)
    source_ids: list[str] = []
    citations = []
    rejected: list[dict] = []

    for item in body.items:
        payload = item.model_dump()
        if body.target == "source_library":
            source_ids.append(str(source_service.add_search_result(book, payload).id))
            continue

        citeability, missing = citation_metadata(item.source_type, payload)
        if not citeability:
            rejected.append({"id": item.id, "title": item.title, "reason": "文献元数据不完整", "metadata_missing": missing})
            continue
        paper = {
            "title": item.title,
            "year": item.year,
            "authors": item.authors,
            "journal": item.journal or item.publisher,
            "doi": item.doi,
            "source": item.provider,
            "source_label": item.provider,
            "external_id": item.doi or item.isbn or item.external_id or item.url,
            "abstract_preview": item.snippet,
            "url": item.url,
            "document_type": item.document_type or item.source_type,
            "publisher": item.publisher,
        }
        citations.append(
            create_citation_from_paper(db, book, paper, source=CitationSource.literature_search)
        )

    db.commit()
    source_rows = source_service.list_sources(book) if source_ids else []
    sources = [
        SourceOut.model_validate(row)
        for row in source_rows
        if str(row["id"]) in source_ids
    ]
    return SourceSearchResultAddOut(
        target=body.target,
        added_count=len(sources) if body.target == "source_library" else len(citations),
        sources=sources,
        citations=[CitationOut.model_validate(row) for row in citations],
        rejected=rejected,
    )


@router.get("/{book_id}/sources", response_model=list[SourceOut])
def list_sources(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = SourceLibraryService(db)
    queued = svc.ensure_missing_upload_indexes(book)
    if queued:
        from app.services.sources.source_ingestion_service import run_source_index_task

        db.commit()
        for item, ref in queued:
            background_tasks.add_task(run_source_index_task, book.id, item.id, ref.id)
    rows = svc.list_sources(book)
    return [SourceOut.model_validate(r) for r in rows]


@router.post("/{book_id}/sources", response_model=SourceOut)
def paste_source(
    book_id: UUID,
    body: PasteSourceIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    item = SourceLibraryService(db).add_pasted_text(book, body.text)
    db.commit()
    rows = SourceLibraryService(db).list_sources(book)
    match = next((r for r in rows if str(r["id"]) == str(item.id)), None)
    if not match:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to load source")
    return SourceOut.model_validate(match)


@router.post("/{book_id}/sources/upload", response_model=SourceOut)
async def upload_source(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    item = SourceLibraryService(db).add_upload(
        book,
        filename=file.filename or "upload.bin",
        content=content,
        owner_user_id=user.id,
        mime_type=file.content_type,
    )
    db.commit()
    if item.reference_file_id:
        from app.services.sources.source_ingestion_service import run_source_index_task

        background_tasks.add_task(run_source_index_task, book.id, item.id, item.reference_file_id)
    rows = SourceLibraryService(db).list_sources(book)
    match = next((r for r in rows if str(r["id"]) == str(item.id)), None)
    if not match:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to load source")
    return SourceOut.model_validate(match)


@router.delete("/{book_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    book_id: UUID,
    source_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = SourceLibraryService(db)
    try:
        svc.remove_source(book, source_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    db.commit()


@router.post("/{book_id}/sources/{source_id}/read", response_model=SourceOut)
def read_source(
    book_id: UUID,
    source_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = SourceLibraryService(db)
    try:
        item = svc.read_source(book, source_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    db.commit()
    if getattr(item, "reference_file_id", None):
        from app.services.sources.source_ingestion_service import run_source_index_task

        ref = db.get(ReferenceFile, item.reference_file_id)
        if ref and ref.parse_status == ParseStatus.pending:
            background_tasks.add_task(run_source_index_task, book.id, item.id, item.reference_file_id)
    rows = svc.list_sources(book)
    match = next((r for r in rows if str(r["id"]) == str(source_id)), None)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return SourceOut.model_validate(match)


@router.post("/{book_id}/sources/segments/{segment_id}/confirm", response_model=SourceSegmentOut)
def confirm_source_segment(
    book_id: UUID,
    segment_id: UUID,
    body: ConfirmSegmentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = SourceSegmentService(db)
    try:
        seg = svc.confirm_segment(book, segment_id, confirmed=body.confirmed)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    db.commit()
    rows = svc.segments_to_dict([seg])
    if not rows:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to load segment")
    return SourceSegmentOut.model_validate(rows[0])
