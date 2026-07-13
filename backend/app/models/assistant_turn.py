"""Project assistant turns and reasoning traces."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AssistantTurn(Base):
    __tablename__ = "assistant_turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    assistant_message = Column(Text, nullable=False)
    basis_patch = Column(JSONB, nullable=True)
    tool_calls = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    traces = relationship("AssistantTrace", back_populates="turn", cascade="all, delete-orphan")


class AssistantTrace(Base):
    __tablename__ = "assistant_traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turn_id = Column(UUID(as_uuid=True), ForeignKey("assistant_turns.id", ondelete="CASCADE"), nullable=False, index=True)
    claim = Column(Text, nullable=False)
    evidence = Column(JSONB, nullable=True)
    reason_summary = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    turn = relationship("AssistantTurn", back_populates="traces")
