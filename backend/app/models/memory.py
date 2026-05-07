import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MemoryType(str, enum.Enum):
    style = "style"
    term = "term"
    summary = "summary"
    citation = "citation"


class BookMemory(Base):
    __tablename__ = "book_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_index = Column(Integer, nullable=False, default=0)
    type = Column(Enum(MemoryType, name="memory_type"), nullable=False)
    key = Column(String(500), nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
