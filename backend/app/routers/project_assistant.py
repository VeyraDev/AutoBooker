"""Project startup assistant API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.project_assistant import (
    PasteSourceIn,
    SourceOut,
    ToolResultOut,
    ConfirmationOut,
    TraceOut,
    TurnIn,
    TurnListItem,
    TurnOut,
)
from app.schemas.project_memory import ProjectMemoryOut
from app.schemas.writing_basis import WritingBasisOut
from app.services import book_service
from app.services.assistant.project_assistant_service import ProjectAssistantService

router = APIRouter(prefix="/books", tags=["project-assistant"])


@router.post("/{book_id}/project-assistant/turns", response_model=TurnOut)
def create_turn(
    book_id: UUID,
    body: TurnIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = ProjectAssistantService(db)
    try:
        result = svc.run_turn(book, user, body.message, chapter_index=body.chapter_index)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    db.commit()
    return TurnOut(
        turn_id=result["turn_id"],
        assistant_message=result["assistant_message"],
        writing_basis=WritingBasisOut.model_validate(result["writing_basis"]) if result.get("writing_basis") else None,
        traces=[TraceOut.model_validate(t) for t in result.get("traces") or []],
        sources=[SourceOut.model_validate(s) for s in result.get("sources") or []],
        open_questions=result.get("open_questions") or [],
        memories=[ProjectMemoryOut.model_validate(m) for m in result.get("memories") or []],
        tool_results=[ToolResultOut.model_validate(t) for t in result.get("tool_results") or []],
        pending_confirmations=[ConfirmationOut.model_validate(c) for c in result.get("pending_confirmations") or []],
    )


@router.get("/{book_id}/project-assistant/turns", response_model=list[TurnListItem])
def list_turns(
    book_id: UUID,
    page: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    rows = ProjectAssistantService(db).list_turns(book_id, page=page)
    return rows


@router.get("/{book_id}/project-assistant/traces", response_model=list[TraceOut])
def list_traces(
    book_id: UUID,
    turn_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    rows = ProjectAssistantService(db).list_traces(book_id, turn_id=turn_id)
    return rows
