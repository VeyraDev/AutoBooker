import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BookType(str, enum.Enum):
    nonfiction = "nonfiction"
    academic = "academic"


class BookStatus(str, enum.Enum):
    setup = "setup"
    outline_generating = "outline_generating"
    outline_ready = "outline_ready"
    writing = "writing"
    review_ready = "review_ready"
    completed = "completed"


class CitationStyle(str, enum.Enum):
    apa = "apa"
    mla = "mla"
    chicago = "chicago"
    gb_t7714 = "gb_t7714"


class Book(Base):
    __tablename__ = "books"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    book_type = Column(Enum(BookType, name="book_type"), nullable=False)
    discipline = Column(String(100))
    target_audience = Column(String(500))
    citation_style = Column(Enum(CitationStyle, name="citation_style"))
    target_words = Column(Integer, default=80000)
    status = Column(Enum(BookStatus, name="book_status"), default=BookStatus.setup, nullable=False)
    ai_model = Column(String(50), default="claude-3-5-sonnet")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="books")
    chapters = relationship(
        "Chapter",
        back_populates="book",
        order_by="Chapter.index",
        cascade="all, delete-orphan",
    )
