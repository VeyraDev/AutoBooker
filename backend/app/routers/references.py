"""Reference file upload, list, status, and RAG search (debug)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.reference import ParseStatus, ReferenceFile
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.reference import (
    ParseStatusOut,
    ReferenceFileOut,
    ReferenceSearchIn,
    ReferenceSearchOut,
    ReferenceUploadOut,
)
from app.services import book_service
from app.agents.document_parser import DocumentParserAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["references"])


def _run_parse_task(book_id: UUID, file_id: UUID, storage_path: str, file_type: str) -> None:
    db = SessionLocal()
    try:
        agent = DocumentParserAgent(db, book_id)
        agent.parse_and_store(file_id, storage_path, file_type)
    except Exception:
        logger.exception("background parse failed book=%s file=%s", book_id, file_id)
    finally:
        db.close()


ALLOWED = {".pdf", ".docx"}


@router.post(
    "/{book_id}/references/upload",
    response_model=ReferenceUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reference(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only {', '.join(sorted(ALLOWED))} are allowed",
        )
    file_type = "pdf" if suffix == ".pdf" else "docx"

    from app.config import settings

    base = settings.upload_path / str(book.id)
    base.mkdir(parents=True, exist_ok=True)
    new_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    dest = base / new_name

    content = await file.read()
    dest.write_bytes(content)

    ref = ReferenceFile(
        book_id=book.id,
        filename=file.filename,
        storage_path=str(dest),
        file_type=file_type,
        parse_status=ParseStatus.pending,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)

    background_tasks.add_task(
        _run_parse_task,
        book.id,
        ref.id,
        str(dest),
        file_type,
    )

    return ReferenceUploadOut(
        id=ref.id,
        filename=ref.filename,
        file_type=ref.file_type,
        parse_status=ParseStatusOut(ref.parse_status.value),
        message="uploaded, parsing in background",
    )


@router.get("/{book_id}/references", response_model=list[ReferenceFileOut])
def list_references(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    rows = (
        db.query(ReferenceFile)
        .filter(ReferenceFile.book_id == book_id)
        .order_by(ReferenceFile.created_at.desc())
        .all()
    )
    return rows


@router.get("/{book_id}/references/{file_id}/status", response_model=ReferenceFileOut)
def reference_status(
    book_id: UUID,
    file_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ref = db.query(ReferenceFile).filter(ReferenceFile.id == file_id, ReferenceFile.book_id == book_id).first()
    if not ref:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")
    return ref


@router.post("/{book_id}/references/search", response_model=ReferenceSearchOut)
def search_references(
    book_id: UUID,
    body: ReferenceSearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    agent = DocumentParserAgent(db, book_id)
    snippets = agent.retrieve(body.query, top_k=body.top_k)
    return ReferenceSearchOut(snippets=snippets)
