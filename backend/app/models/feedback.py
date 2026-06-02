"""用户意见反馈。"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class FeedbackType(str, enum.Enum):
    bug = "bug"
    feature = "feature"
    experience = "experience"
    other = "other"


class FeedbackStatus(str, enum.Enum):
    open = "open"
    replied = "replied"
    closed = "closed"


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(FeedbackType, name="feedback_type"), nullable=False)
    status = Column(Enum(FeedbackStatus, name="feedback_status"), nullable=False, default=FeedbackStatus.open)
    content = Column(Text, nullable=False)
    page_url = Column(String(500), nullable=True)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="SET NULL"), nullable=True)
    meta_json = Column(JSONB, nullable=True)
    reply = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
