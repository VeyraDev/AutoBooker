"""Project memory CRUD API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.project_memory import ProjectMemoryOut, ProjectMemoryPatchIn
from app.services import book_service
from app.services.assistant.project_memory_service import ProjectMemoryService

router = APIRouter(prefix="/books", tags=["memories"])


@router.get("/{book_id}/memories", response_model=list[ProjectMemoryOut])
def list_memories(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    return ProjectMemoryService(db).list_memories(book_id)


@router.patch("/{book_id}/memories/{memory_id}", response_model=ProjectMemoryOut)
def patch_memory(
    book_id: UUID,
    memory_id: UUID,
    body: ProjectMemoryPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    svc = ProjectMemoryService(db)
    row = svc.get_or_none(book_id, memory_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    try:
        svc.patch(row, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()
    return row


@router.delete("/{book_id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    book_id: UUID,
    memory_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    svc = ProjectMemoryService(db)
    row = svc.get_or_none(book_id, memory_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    svc.delete(row)
    db.commit()
