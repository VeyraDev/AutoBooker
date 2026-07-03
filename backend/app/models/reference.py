import enum
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class OutlineUsage(str, enum.Enum):
    primary = "primary"
    reference = "reference"


class FileLifecycleStatus(str, enum.Enum):
    processing = "processing"
    pending_confirmation = "pending_confirmation"
    effective = "effective"
    disabled = "disabled"
    failed = "failed"


class FilePurpose(str, enum.Enum):
    outline = "outline"
    writing_requirements = "writing_requirements"
    reference_material = "reference_material"
    bibliography = "bibliography"
    source_manuscript = "source_manuscript"


class ReferenceFile(Base):
    __tablename__ = "reference_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    storage_path = Column(String(2000), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf | docx | txt
    ingest_kind = Column(String(20), nullable=False, default="reference")  # reference | material
    parse_status = Column(
        Enum(ParseStatus, name="parse_status"),
        default=ParseStatus.pending,
        nullable=False,
    )
    error_message = Column(Text)
    parsed_at = Column(DateTime(timezone=True))
    share_to_library = Column(String(20), nullable=False, default="private")  # private | pending | shared
    file_purposes = Column(JSONB, nullable=True)  # outline | writing_requirements | reference
    outline_usage = Column(
        Enum(OutlineUsage, name="outline_usage"),
        nullable=True,
    )
    user_note = Column(Text, nullable=True)
    parse_version = Column(Integer, nullable=False, default=0, server_default="0")
    parse_artifacts = Column(JSONB, nullable=True)
    lifecycle_status = Column(
        Enum(FileLifecycleStatus, name="file_lifecycle_status"),
        nullable=False,
        default=FileLifecycleStatus.processing,
        server_default=FileLifecycleStatus.processing.value,
    )
    disabled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chunks = relationship("ReferenceChunk", back_populates="file", cascade="all, delete-orphan")
    purposes = relationship("ReferenceFilePurpose", back_populates="file", cascade="all, delete-orphan")


class ReferenceFilePurpose(Base):
    __tablename__ = "reference_file_purposes"
    __table_args__ = (UniqueConstraint("file_id", "purpose", name="uq_reference_file_purpose"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(Enum(FilePurpose, name="file_purpose"), nullable=False)
    confidence = Column(Integer, nullable=False, default=100)
    user_confirmed = Column(Boolean, nullable=False, default=True, server_default="true")
    is_primary = Column(Boolean, nullable=False, default=False, server_default="false")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    file = relationship("ReferenceFile", back_populates="purposes")


class ReferenceChunk(Base):
    __tablename__ = "reference_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    chunk_kind = Column(String(32), nullable=False, default="reference_material", server_default="reference_material")
    page_number = Column(Integer, nullable=True)
    paragraph_index = Column(Integer, nullable=True)
    heading_path = Column(JSONB, nullable=True)
    directly_quotable = Column(Boolean, nullable=False, default=False, server_default="false")
    active = Column(Boolean, nullable=False, default=True, server_default="true")

    file = relationship("ReferenceFile", back_populates="chunks")
