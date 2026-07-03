import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BookType(str, enum.Enum):
    nonfiction = "nonfiction"
    academic = "academic"


class BookStatus(str, enum.Enum):
    setup = "setup"
    outline_generating = "outline_generating"
    outline_ready = "outline_ready"
    auto_generating = "auto_generating"
    writing = "writing"
    review_ready = "review_ready"
    completed = "completed"


class CitationStyle(str, enum.Enum):
    apa = "apa"
    mla = "mla"
    chicago = "chicago"
    gb_t7714 = "gb_t7714"


class BookWorkflowMode(str, enum.Enum):
    from_scratch = "from_scratch"
    optimize_existing = "optimize_existing"


class Book(Base):
    __tablename__ = "books"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    workflow_mode = Column(
        Enum(BookWorkflowMode, name="book_workflow_mode"),
        nullable=False,
        default=BookWorkflowMode.from_scratch,
        server_default=BookWorkflowMode.from_scratch.value,
    )
    original_title = Column(String(500), nullable=True)
    allow_title_optimization = Column(Boolean, nullable=False, default=False, server_default="false")
    book_type = Column(Enum(BookType, name="book_type"), nullable=False)
    discipline = Column(String(100))
    disciplines = Column(JSONB, nullable=True)
    target_audience = Column(String(500))
    citation_style = Column(Enum(CitationStyle, name="citation_style"))
    structured_citations = Column(Boolean, nullable=False, default=False, server_default="false")
    target_words = Column(Integer, default=80000)
    style_type = Column(String(50), nullable=True)
    topic_tags = Column(JSONB, nullable=True)
    topic_brief = Column(Text, nullable=True)
    user_material = Column(Text, nullable=True)
    ai_inferred_settings = Column(JSONB, nullable=True)
    setup_recommendation_cache = Column(JSONB, nullable=True)
    narrative_constitution = Column(Text, nullable=True)
    narrative_constitution_outline_hash = Column(String(64), nullable=True)
    constitution_stale = Column(Boolean, nullable=False, default=False, server_default="false")
    material_conflicts = Column(JSONB, nullable=True)
    preface = Column(JSONB, nullable=True)
    status = Column(Enum(BookStatus, name="book_status"), default=BookStatus.setup, nullable=False)
    last_literature_query = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="books")
    chapters = relationship(
        "Chapter",
        back_populates="book",
        order_by="Chapter.index",
        cascade="all, delete-orphan",
    )
    citations = relationship("Citation", back_populates="book", cascade="all, delete-orphan")
    figures = relationship("Figure", back_populates="book", cascade="all, delete-orphan")
