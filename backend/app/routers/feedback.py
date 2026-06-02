"""意见反馈 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feedback import Feedback, FeedbackStatus, FeedbackType
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackIn, FeedbackOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut)
def submit_feedback(
    body: FeedbackIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ft = body.type if body.type in {t.value for t in FeedbackType} else FeedbackType.other.value
    row = Feedback(
        user_id=user.id,
        type=FeedbackType(ft),
        content=body.content.strip(),
        page_url=body.page_url,
        book_id=UUID(body.book_id) if body.book_id else None,
        meta_json={"user_agent": request.headers.get("user-agent", "")[:300]},
        status=FeedbackStatus.open,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FeedbackOut(
        id=str(row.id),
        type=row.type.value,
        status=row.status.value,
        content=row.content,
        reply=row.reply,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


@router.get("/mine", response_model=list[FeedbackOut])
def my_feedback(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Feedback).filter(Feedback.user_id == user.id).order_by(Feedback.created_at.desc()).limit(30).all()
    return [
        FeedbackOut(
            id=str(r.id),
            type=r.type.value,
            status=r.status.value,
            content=r.content,
            reply=r.reply,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
