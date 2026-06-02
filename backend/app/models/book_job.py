"""一键生成书稿 Job。"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class BookJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class BookJobStep(str, enum.Enum):
    setting = "setting"
    narrative = "narrative"
    literature = "literature"
    outline = "outline"
    preface = "preface"
    writing = "writing"
    bibliography = "bibliography"
    done = "done"


class BookJob(Base):
    __tablename__ = "book_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(BookJobStatus, name="book_job_status"), nullable=False, default=BookJobStatus.pending)
    current_step = Column(Enum(BookJobStep, name="book_job_step"), nullable=True)
    progress_pct = Column(Integer, nullable=False, default=0)
    checkpoint_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
