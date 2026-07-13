"""Review task — scope/standards sheet before each review run."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class ReviewTaskScope(str, enum.Enum):
    book = "book"
    chapter = "chapter"
    custom = "custom"


class ReviewTaskGoal(str, enum.Enum):
    default = "default"
    custom = "custom"


class ReviewTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    scope = Column(Enum(ReviewTaskScope, name="review_task_scope"), nullable=False, default=ReviewTaskScope.book)
    chapter_indexes = Column(JSONB, nullable=True)
    goal = Column(Enum(ReviewTaskGoal, name="review_task_goal"), nullable=False, default=ReviewTaskGoal.default)
    custom_prompt = Column(Text, nullable=True)
    adopted_standards = Column(JSONB, nullable=False, default=dict)
    exclusions = Column(JSONB, nullable=False, default=list)
    output_threshold = Column(String(32), nullable=False, default="all_tiers")
    status = Column(Enum(ReviewTaskStatus, name="review_task_status"), nullable=False, default=ReviewTaskStatus.pending)
    context_snapshot_hash = Column(String(80), nullable=True)
    summary_text = Column(Text, nullable=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("book_review_stage_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
