"""Book-level review stage models."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class ReviewStageStatus(str, enum.Enum):
    not_started = "not_started"
    running = "running"
    completed = "completed"
    failed = "failed"


class ReviewTrack(str, enum.Enum):
    writing_quality = "writing_quality"
    publication_standard = "publication_standard"


class ReviewFindingStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class BookReviewStageRun(Base):
    __tablename__ = "book_review_stage_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(ReviewStageStatus, name="review_stage_status"), nullable=False, default=ReviewStageStatus.not_started)
    writing_quality_status = Column(Enum(ReviewStageStatus, name="review_stage_status", create_type=False), nullable=True)
    publication_standard_status = Column(Enum(ReviewStageStatus, name="review_stage_status", create_type=False), nullable=True)
    summary_json = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BookReviewFinding(Base):
    __tablename__ = "book_review_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("book_review_stage_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    track = Column(Enum(ReviewTrack, name="review_track"), nullable=False)
    category = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False, default="medium")
    status = Column(Enum(ReviewFindingStatus, name="review_finding_status"), nullable=False, default=ReviewFindingStatus.open)
    title = Column(String(500), nullable=False)
    detail = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    source_ref_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
