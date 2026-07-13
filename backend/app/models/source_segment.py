"""Source segment — mixed-file role slices linked to intake items."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SegmentType(str, enum.Enum):
    outline = "outline"
    requirement = "requirement"
    manuscript = "manuscript"
    preface = "preface"
    chapter_draft = "chapter_draft"
    bibliography = "bibliography"
    style_sample = "style_sample"
    case_material = "case_material"
    table_material = "table_material"
    figure_material = "figure_material"


class SourceSegment(Base):
    __tablename__ = "source_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("intake_items.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_type = Column(Enum(SegmentType, name="source_segment_type"), nullable=False)
    summary = Column(Text, nullable=False)
    locator = Column(String(500), nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    suggested_usage = Column(Text, nullable=True)
    excerpt = Column(Text, nullable=True)
    user_confirmed = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
