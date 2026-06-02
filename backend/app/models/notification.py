"""站内通知。"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class NotificationType(str, enum.Enum):
    system = "system"
    book_job = "book_job"
    feedback_reply = "feedback_reply"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(NotificationType, name="notification_type"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    payload_json = Column(JSONB, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
