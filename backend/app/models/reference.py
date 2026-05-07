import enum
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class ReferenceFile(Base):
    __tablename__ = "reference_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    storage_path = Column(String(2000), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf | docx
    parse_status = Column(
        Enum(ParseStatus, name="parse_status"),
        default=ParseStatus.pending,
        nullable=False,
    )
    error_message = Column(Text)
    parsed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chunks = relationship("ReferenceChunk", back_populates="file", cascade="all, delete-orphan")


class ReferenceChunk(Base):
    __tablename__ = "reference_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)

    file = relationship("ReferenceFile", back_populates="chunks")
