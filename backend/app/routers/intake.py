"""Project intake API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.intake import CreationOrigin, IntakeItemType, UnderstandingStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.services import book_service
from app.services.intake.intake_services import IntakeItemService
from app.services.writing.writing_basis_service import WritingBasisService

router = APIRouter(prefix="/books", tags=["intake"])

_INTAKE_DEPRECATED_MSG = "旧 Intake 向导已下线，请使用项目启动助手（/project-assistant/turns）"


def _deprecated_intake_write() -> None:
    raise HTTPException(status.HTTP_410_GONE, _INTAKE_DEPRECATED_MSG)


class ProjectStartBootstrapIn(BaseModel):
    creation_origin: CreationOrigin = CreationOrigin.idea_only
    raw_goal_text: str | None = None
    negative_constraints_text: str | None = None


class IntakeInitIn(BaseModel):
    creation_origin: CreationOrigin
    raw_goal_text: str | None = None
    negative_constraints_text: str | None = None


class IntakeItemIn(BaseModel):
    item_type: IntakeItemType
    text_content: str = Field(min_length=1)


class UnderstandingPatchIn(BaseModel):
    correction: str = Field(min_length=1)


class WritingPlanPatchIn(BaseModel):
    user_facing_text: str | None = None


@router.post("/{book_id}/project-start/complete")
def complete_project_start(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """项目启动助手阶段完成：确认 intake，同步主题说明，进入大纲页。"""
    from app.models.intake import IntakeStatus, ProjectIntake

    book = book_service.get_book_or_404(book_id, user, db)
    intake = (
        db.query(ProjectIntake)
        .filter(ProjectIntake.book_id == book.id, ProjectIntake.status != IntakeStatus.superseded)
        .order_by(ProjectIntake.created_at.desc())
        .first()
    )
    if not intake:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Intake not initialized")
    goal = (intake.raw_goal_text or "").strip()
    if goal and not (book.topic_brief or "").strip():
        book.topic_brief = goal[:20_000]
    if goal and not (book.user_material or "").strip():
        book.user_material = goal[:50_000]
    intake.status = IntakeStatus.confirmed
    db.commit()
    return {"intake_id": str(intake.id), "status": intake.status.value}


@router.post("/{book_id}/project-start/bootstrap")
def bootstrap_project_start(
    book_id: UUID,
    body: ProjectStartBootstrapIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """幂等创建 intake + WritingBasis 草稿，供新书进入助手路径。"""
    book = book_service.get_book_or_404(book_id, user, db)
    book.creation_origin = body.creation_origin
    svc = IntakeItemService(db)
    intake = svc.get_or_create_intake(book, body.creation_origin)
    if body.raw_goal_text is not None:
        intake.raw_goal_text = body.raw_goal_text
    if body.negative_constraints_text is not None:
        intake.negative_constraints_text = body.negative_constraints_text

    basis_svc = WritingBasisService(db)
    basis = basis_svc.get_draft_or_create(book)
    goal = (body.raw_goal_text or intake.raw_goal_text or "").strip()
    if goal:
        patch: dict[str, str] = {}
        if not (basis.direction or "").strip():
            patch["direction"] = goal[:2000]
        if not (basis.book_promise or "").strip():
            patch["book_promise"] = goal[:4000]
        if patch:
            basis_svc.patch(basis, patch)

    db.commit()
    return {
        "intake_id": str(intake.id),
        "status": intake.status.value,
        "writing_basis_id": str(basis.id),
    }


@router.post("/{book_id}/intake/init")
def init_intake(
    book_id: UUID,
    body: IntakeInitIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _deprecated_intake_write()


@router.post("/{book_id}/intake/items")
def add_intake_item(
    book_id: UUID,
    body: IntakeItemIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _deprecated_intake_write()


@router.post("/{book_id}/intake/items/upload")
async def upload_intake_item(
    book_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _deprecated_intake_write()


@router.get("/{book_id}/intake")
def get_intake(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book = book_service.get_book_or_404(book_id, user, db)
    from app.models.intake import ProjectIntake, IntakeItem, InputUnderstanding, WritingPlan

    intake = (
        db.query(ProjectIntake)
        .filter(ProjectIntake.book_id == book.id)
        .order_by(ProjectIntake.created_at.desc())
        .first()
    )
    if not intake:
        return {"intake": None}
    items = db.query(IntakeItem).filter(IntakeItem.intake_id == intake.id).all()
    understanding = (
        db.query(InputUnderstanding)
        .filter(InputUnderstanding.intake_id == intake.id, InputUnderstanding.status != UnderstandingStatus.superseded)
        .order_by(InputUnderstanding.version.desc())
        .first()
    )
    plan = (
        db.query(WritingPlan)
        .filter(WritingPlan.intake_id == intake.id)
        .order_by(WritingPlan.version.desc())
        .first()
    )
    return {
        "intake": {
            "id": str(intake.id),
            "creation_origin": intake.creation_origin.value,
            "status": intake.status.value,
            "raw_goal_text": intake.raw_goal_text,
            "negative_constraints_text": intake.negative_constraints_text,
            "items": [{"id": str(i.id), "type": i.item_type.value, "text": i.text_content} for i in items],
            "understanding": {
                "id": str(understanding.id),
                "version": understanding.version,
                "user_facing_text": understanding.user_facing_text,
                "unclear_questions": understanding.unclear_questions,
            }
            if understanding
            else None,
            "writing_plan": {
                "id": str(plan.id),
                "version": plan.version,
                "user_facing_text": plan.user_facing_text,
                "status": plan.status.value,
            }
            if plan
            else None,
        }
    }


@router.post("/{book_id}/intake/understand")
def generate_understanding(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _deprecated_intake_write()


@router.patch("/{book_id}/intake/understanding")
def patch_understanding(
    book_id: UUID,
    body: UnderstandingPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _deprecated_intake_write()


@router.post("/{book_id}/intake/confirm")
def confirm_understanding(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _deprecated_intake_write()


@router.post("/{book_id}/writing-plan/generate")
def generate_writing_plan(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _deprecated_intake_write()


@router.patch("/{book_id}/writing-plan")
def patch_writing_plan(
    book_id: UUID,
    body: WritingPlanPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _deprecated_intake_write()


@router.post("/{book_id}/writing-plan/confirm")
def confirm_writing_plan(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _deprecated_intake_write()
