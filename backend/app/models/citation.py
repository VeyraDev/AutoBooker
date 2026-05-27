import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
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
