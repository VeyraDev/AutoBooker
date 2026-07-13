"""Long-term project memory for assistant conversations."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ProjectMemoryType(str, enum.Enum):
    fact = "fact"
    decision = "decision"
    constraint = "constraint"
    open_question = "open_question"
    risk = "risk"


class ProjectMemoryStrength(str, enum.Enum):
    must = "must"
    should = "should"
    preference = "preference"


class ProjectMemory(Base):
    __tablename__ = "project_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(
        Enum(ProjectMemoryType, name="project_memory_type"),
        nullable=False,
        default=ProjectMemoryType.fact,
    )
    content = Column(Text, nullable=False)
    source_turn_id = Column(UUID(as_uuid=True), ForeignKey("assistant_turns.id", ondelete="SET NULL"), nullable=True)
    strength = Column(
        Enum(ProjectMemoryStrength, name="project_memory_strength"),
        nullable=False,
        default=ProjectMemoryStrength.should,
    )
    confirmed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
