import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class GenerationContextSnapshot(Base):
    __tablename__ = "generation_context_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    understanding_id = Column(UUID(as_uuid=True), nullable=True)
    writing_plan_id = Column(UUID(as_uuid=True), nullable=True)
    writing_basis_id = Column(UUID(as_uuid=True), nullable=True)
    requirement_ids = Column(JSONB, nullable=False, default=list)
    outline_constraint_ids = Column(JSONB, nullable=False, default=list)
    source_items = Column(JSONB, nullable=False, default=list)
    context_hash = Column(String(64), nullable=False)
    prompt_excerpt = Column(Text, nullable=True)
    source_module = Column(String(32), nullable=False)
    chapter_index = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
