import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class ConfirmationStatus(str, enum.Enum):
    effective = "effective"
    pending = "pending"
    disabled = "disabled"


class WritingRequirement(Base):
    __tablename__ = "writing_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    category = Column(String(64), nullable=False, default="general")
    strength = Column(String(20), nullable=False, default="should")
    scope = Column(String(20), nullable=False, default="book")
    chapter_index = Column(Integer, nullable=True)
    confirmation_status = Column(
        Enum(ConfirmationStatus, name="material_confirmation_status"),
        nullable=False,
        default=ConfirmationStatus.effective,
    )
    validation_kind = Column(String(64), nullable=True)
    validation_config = Column(JSONB, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaterialTerm(Base):
    __tablename__ = "material_terms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False, index=True)
    term = Column(String(300), nullable=False)
    canonical_form = Column(String(300), nullable=True)
    definition = Column(Text, nullable=True)
    term_type = Column(String(40), nullable=False, default="domain_term")
    confirmation_status = Column(
        Enum(ConfirmationStatus, name="material_confirmation_status", create_type=False),
        nullable=False,
        default=ConfirmationStatus.effective,
    )
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaterialConflict(Base):
    __tablename__ = "material_conflicts_v2"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    conflict_type = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    file_ids = Column(JSONB, nullable=False, default=list)
    details = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    resolution = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class OutlineConstraint(Base):
    __tablename__ = "outline_constraints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_index = Column(Integer, nullable=False)
    chapter_title = Column(String(500), nullable=False)
    locked_sections = Column(JSONB, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RequirementValidation(Base):
    __tablename__ = "requirement_validations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requirement_id = Column(UUID(as_uuid=True), ForeignKey("writing_requirements.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    passed = Column(Boolean, nullable=False)
    detail = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
