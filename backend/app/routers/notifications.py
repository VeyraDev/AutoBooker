"""站内通知 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.feedback import NotificationListOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read.is_(False)).count()
    items = [
        NotificationOut(
            id=str(r.id),
            type=r.type.value,
            title=r.title,
            body=r.body,
            payload_json=r.payload_json,
            is_read=r.is_read,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
    return NotificationListOut(items=items, unread_count=unread)


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(Notification, notification_id)
    if row and str(row.user_id) == str(user.id):
        row.is_read = True
        db.commit()
    return {"ok": True}


@router.get("/community-qr")
def community_qr():
    return {"url": settings.COMMUNITY_QR_URL or ""}
