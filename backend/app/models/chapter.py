import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ChapterStatus(str, enum.Enum):
    pending = "pending"
    generating = "generating"
    done = "done"


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    index = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    content = Column(JSONB)
    word_count = Column(Integer, default=0)
    status = Column(Enum(ChapterStatus, name="chapter_status"), default=ChapterStatus.pending, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    book = relationship("Book", back_populates="chapters")
