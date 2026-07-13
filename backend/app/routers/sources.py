"""Source library API (intake items unified view)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.project_assistant import ConfirmSegmentIn, PasteSourceIn, SourceOut, SourceSegmentOut
from app.services import book_service
from app.services.sources.source_library_service import SourceLibraryService
from app.services.sources.source_segment_service import SourceSegmentService

router = APIRouter(prefix="/books", tags=["sources"])


@router.get("/{book_id}/sources", response_model=list[SourceOut])
def list_sources(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    rows = SourceLibraryService(db).list_sources(book)
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = SourceLibraryService(db)
    try:
        svc.read_source(book, source_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    db.commit()
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
