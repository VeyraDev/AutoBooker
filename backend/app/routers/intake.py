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
from app.services.intake.intake_services import (
    ConstraintSink,
    InputUnderstandingService,
    IntakeItemService,
    WritingPlanService,
)

router = APIRouter(prefix="/books", tags=["intake"])


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


@router.post("/{book_id}/intake/init")
def init_intake(
    book_id: UUID,
    body: IntakeInitIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    book.creation_origin = body.creation_origin
    svc = IntakeItemService(db)
    intake = svc.get_or_create_intake(book, body.creation_origin)
    intake.raw_goal_text = body.raw_goal_text
    intake.negative_constraints_text = body.negative_constraints_text
    db.commit()
    return {"intake_id": str(intake.id), "status": intake.status.value}


@router.post("/{book_id}/intake/items")
def add_intake_item(
    book_id: UUID,
    body: IntakeItemIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    if not book.creation_origin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Call intake/init first")
    svc = IntakeItemService(db)
    intake = svc.get_or_create_intake(book, CreationOrigin(book.creation_origin))
    item = svc.add_text_item(intake, body.text_content, body.item_type)
    db.commit()
    return {"item_id": str(item.id)}


@router.post("/{book_id}/intake/items/upload")
async def upload_intake_item(
    book_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    if not book.creation_origin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Call intake/init first")
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    svc = IntakeItemService(db)
    intake = svc.get_or_create_intake(book, CreationOrigin(book.creation_origin))
    item = svc.add_upload_item(
        intake,
        filename=file.filename or "upload.bin",
        content=content,
        owner_user_id=user.id,
        mime_type=file.content_type,
    )
    db.commit()
    return {"item_id": str(item.id), "detected_roles": item.detected_roles or []}


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
    book = book_service.get_book_or_404(book_id, user, db)
    from app.models.intake import ProjectIntake

    intake = db.query(ProjectIntake).filter(ProjectIntake.book_id == book.id).order_by(ProjectIntake.created_at.desc()).first()
    if not intake:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Intake not initialized")
    u = InputUnderstandingService(db).generate(book, intake)
    db.commit()
    return {"understanding_id": str(u.id), "user_facing_text": u.user_facing_text}


@router.patch("/{book_id}/intake/understanding")
def patch_understanding(
    book_id: UUID,
    body: UnderstandingPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    from app.models.intake import InputUnderstanding

    u = (
        db.query(InputUnderstanding)
        .filter(InputUnderstanding.book_id == book_id)
        .order_by(InputUnderstanding.version.desc())
        .first()
    )
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No understanding")
    new_u = InputUnderstandingService(db).apply_user_correction(u, body.correction)
    db.commit()
    return {"understanding_id": str(new_u.id), "user_facing_text": new_u.user_facing_text}


@router.post("/{book_id}/intake/confirm")
def confirm_understanding(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    from app.models.intake import InputUnderstanding, UnderstandingStatus

    u = (
        db.query(InputUnderstanding)
        .filter(InputUnderstanding.book_id == book_id, InputUnderstanding.status == UnderstandingStatus.draft)
        .order_by(InputUnderstanding.version.desc())
        .first()
    )
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No draft understanding")
    u.status = UnderstandingStatus.confirmed
    db.commit()
    return {"understanding_id": str(u.id), "status": "confirmed"}


@router.post("/{book_id}/writing-plan/generate")
def generate_writing_plan(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book = book_service.get_book_or_404(book_id, user, db)
    from app.models.intake import ProjectIntake, InputUnderstanding, UnderstandingStatus

    intake = db.query(ProjectIntake).filter(ProjectIntake.book_id == book.id).order_by(ProjectIntake.created_at.desc()).first()
    u = (
        db.query(InputUnderstanding)
        .filter(InputUnderstanding.book_id == book.id, InputUnderstanding.status == UnderstandingStatus.confirmed)
        .order_by(InputUnderstanding.version.desc())
        .first()
    )
    if not intake or not u:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Confirm understanding first")
    plan = WritingPlanService(db).generate(book, intake, u)
    db.commit()
    return {"plan_id": str(plan.id), "user_facing_text": plan.user_facing_text}


@router.patch("/{book_id}/writing-plan")
def patch_writing_plan(
    book_id: UUID,
    body: WritingPlanPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    from app.models.intake import WritingPlan, WritingPlanStatus

    plan = (
        db.query(WritingPlan)
        .filter(WritingPlan.book_id == book.id, WritingPlan.status == WritingPlanStatus.draft)
        .order_by(WritingPlan.version.desc())
        .first()
    )
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No draft writing plan")
    if body.user_facing_text is not None:
        text = body.user_facing_text.strip()
        if not text:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Writing plan text cannot be empty")
        plan.user_facing_text = text
    db.commit()
    return {"plan_id": str(plan.id), "user_facing_text": plan.user_facing_text}


@router.post("/{book_id}/writing-plan/confirm")
def confirm_writing_plan(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book = book_service.get_book_or_404(book_id, user, db)
    from app.models.intake import ProjectIntake, InputUnderstanding, WritingPlan, WritingPlanStatus, UnderstandingStatus

    intake = db.query(ProjectIntake).filter(ProjectIntake.book_id == book.id).order_by(ProjectIntake.created_at.desc()).first()
    plan = (
        db.query(WritingPlan)
        .filter(WritingPlan.book_id == book.id, WritingPlan.status == WritingPlanStatus.draft)
        .order_by(WritingPlan.version.desc())
        .first()
    )
    u = (
        db.query(InputUnderstanding)
        .filter(InputUnderstanding.book_id == book.id, InputUnderstanding.status == UnderstandingStatus.confirmed)
        .order_by(InputUnderstanding.version.desc())
        .first()
    )
    if not intake or not plan or not u:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing draft plan or confirmed understanding")
    ConstraintSink(db).confirm_plan(book, intake, plan, u)
    db.commit()
    return {"plan_id": str(plan.id), "status": "confirmed"}
