"""Writing basis API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.intake import InputUnderstanding, ProjectIntake, UnderstandingStatus, WritingPlan, WritingPlanStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.writing_basis import WritingBasisConfirmOut, WritingBasisOut, WritingBasisPatchIn
from app.services import book_service
from app.services.writing.writing_basis_service import WritingBasisService

router = APIRouter(prefix="/books", tags=["writing-basis"])


def _latest_intake(db: Session, book_id: UUID) -> ProjectIntake | None:
    return (
        db.query(ProjectIntake)
        .filter(ProjectIntake.book_id == book_id)
        .order_by(ProjectIntake.created_at.desc())
        .first()
    )


def _latest_understanding_plan(
    db: Session, book_id: UUID
) -> tuple[InputUnderstanding | None, WritingPlan | None]:
    understanding = (
        db.query(InputUnderstanding)
        .filter(
            InputUnderstanding.book_id == book_id,
            InputUnderstanding.status == UnderstandingStatus.confirmed,
        )
        .order_by(InputUnderstanding.version.desc())
        .first()
    )
    if not understanding:
        understanding = (
            db.query(InputUnderstanding)
            .filter(InputUnderstanding.book_id == book_id)
            .order_by(InputUnderstanding.version.desc())
            .first()
        )
    plan = (
        db.query(WritingPlan)
        .filter(WritingPlan.book_id == book_id, WritingPlan.status == WritingPlanStatus.draft)
        .order_by(WritingPlan.version.desc())
        .first()
    )
    if not plan:
        plan = (
            db.query(WritingPlan)
            .filter(WritingPlan.book_id == book_id)
            .order_by(WritingPlan.version.desc())
            .first()
        )
    return understanding, plan


@router.get("/{book_id}/writing-basis", response_model=WritingBasisOut)
def get_writing_basis(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    svc = WritingBasisService(db)
    basis = svc.get_confirmed(book_id) or svc.get_draft(book_id)
    if not basis:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No writing basis found")
    return basis


@router.patch("/{book_id}/writing-basis", response_model=WritingBasisOut)
def patch_writing_basis(
    book_id: UUID,
    body: WritingBasisPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = WritingBasisService(db)
    basis = svc.get_draft(book_id)
    if not basis:
        understanding, plan = _latest_understanding_plan(db, book_id)
        if understanding and plan:
            intake = _latest_intake(db, book_id)
            basis = svc.create_draft_from_intake(book, understanding, plan, intake=intake)
        else:
            basis = svc.create_empty_draft(book)
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty patch")
    try:
        basis = svc.patch(basis, patch)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    db.refresh(basis)
    return basis


@router.post("/{book_id}/writing-basis/confirm", response_model=WritingBasisConfirmOut)
def confirm_writing_basis(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = WritingBasisService(db)
    intake = _latest_intake(db, book_id)
    basis = svc.get_draft(book_id)
    if not basis:
        understanding, plan = _latest_understanding_plan(db, book_id)
        if understanding and plan:
            intake = _latest_intake(db, book_id)
            basis = svc.create_draft_from_intake(book, understanding, plan, intake=intake)
        else:
            basis = svc.create_empty_draft(book)
    try:
        basis = svc.finalize_confirm(book, basis, intake=intake)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    return WritingBasisConfirmOut(basis_id=basis.id, status=basis.status.value)
