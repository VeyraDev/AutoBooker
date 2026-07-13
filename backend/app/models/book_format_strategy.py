"""Book-level format / column strategy for chapter writing."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class FormatStrategyStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    superseded = "superseded"


class BookFormatStrategy(Base):
    __tablename__ = "book_format_strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(
        Enum(FormatStrategyStatus, name="format_strategy_status"),
        nullable=False,
        default=FormatStrategyStatus.draft,
    )
    book_level_columns = Column(JSONB, nullable=False, default=list)
    conditional_columns = Column(JSONB, nullable=False, default=list)
    forbidden_patterns = Column(JSONB, nullable=False, default=list)
    chapter_suggestions = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
