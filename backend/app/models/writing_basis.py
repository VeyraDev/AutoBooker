"""Writing basis — confirmed canonical constraints for downstream writing."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class WritingBasisStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    superseded = "superseded"


class WritingBasis(Base):
    __tablename__ = "writing_bases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(
        Enum(WritingBasisStatus, name="writing_basis_status"),
        nullable=False,
        default=WritingBasisStatus.draft,
    )
    direction = Column(Text, nullable=True)
    book_promise = Column(Text, nullable=True)
    target_readers = Column(Text, nullable=True)
    reader_outcome = Column(Text, nullable=True)
    scope = Column(Text, nullable=True)
    depth = Column(Text, nullable=True)
    voice = Column(Text, nullable=True)
    material_policy = Column(JSONB, nullable=False, default=list)
    outline_policy = Column(JSONB, nullable=False, default=list)
    citation_policy = Column(JSONB, nullable=False, default=list)
    figure_policy = Column(JSONB, nullable=False, default=list)
    must_keep = Column(JSONB, nullable=False, default=list)
    must_avoid = Column(JSONB, nullable=False, default=list)
    open_questions = Column(JSONB, nullable=False, default=list)
    source_understanding_id = Column(UUID(as_uuid=True), nullable=True)
    source_plan_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
