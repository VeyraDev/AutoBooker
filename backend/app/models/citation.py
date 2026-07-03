import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class CitationSource(str, enum.Enum):
    literature_search = "literature_search"
    uploaded_file = "uploaded_file"
    manual = "manual"


class Citation(Base):
    __tablename__ = "citations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    doi = Column(String(200), nullable=True)
    title = Column(String(2000), nullable=False, default="")
    authors = Column(JSONB, nullable=False, default=list)
    year = Column(Integer, nullable=True)
    journal = Column(String(500), nullable=True, default="")
    document_type = Column(String(80), nullable=True)
    publisher = Column(String(500), nullable=True)
    volume = Column(String(80), nullable=True)
    issue = Column(String(80), nullable=True)
    pages = Column(String(120), nullable=True)
    metadata_status = Column(String(32), nullable=False, default="complete", server_default="complete")
    format_cache = Column(JSONB, nullable=True)
    source = Column(
        Enum(CitationSource, name="citation_source"),
        nullable=False,
        default=CitationSource.manual,
    )
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="SET NULL"), nullable=True)
    raw_text = Column(Text, nullable=True)
    external_source = Column(String(64), nullable=True)
    external_id = Column(String(500), nullable=True)
    quotable_snippet = Column(Text, nullable=True)
    abstract_preview = Column(Text, nullable=True)
    url = Column(String(2000), nullable=True)
    list_index = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    book = relationship("Book", back_populates="citations")


class CitationEvidence(Base):
    __tablename__ = "citation_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citation_id = Column(UUID(as_uuid=True), ForeignKey("citations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="SET NULL"), nullable=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("reference_chunks.id", ondelete="SET NULL"), nullable=True)
    page_number = Column(Integer, nullable=True)
    paragraph_locator = Column(String(300), nullable=True)
    heading_path = Column(JSONB, nullable=True)
    quote_text = Column(Text, nullable=False)
    directly_quotable = Column(Boolean, nullable=False, default=False, server_default="false")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CitationOccurrence(Base):
    __tablename__ = "citation_occurrences"
    __table_args__ = (UniqueConstraint("chapter_id", "node_id", name="uq_citation_occurrence_node"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    citation_id = Column(UUID(as_uuid=True), ForeignKey("citations.id", ondelete="RESTRICT"), nullable=False, index=True)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("citation_evidence.id", ondelete="SET NULL"), nullable=True)
    node_id = Column(UUID(as_uuid=True), nullable=False)
    cite_mode = Column(String(24), nullable=False, default="parenthetical")
    locator = Column(String(300), nullable=True)
    prefix = Column(Text, nullable=True)
    suffix = Column(Text, nullable=True)
    ordinal = Column(Integer, nullable=False, default=0)
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    complete = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
