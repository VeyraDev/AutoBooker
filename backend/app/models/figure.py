import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class FigureType(str, enum.Enum):
    flowchart = "flowchart"
    chart = "chart"
    figure = "figure"
    screenshot = "screenshot"


class FigureStatus(str, enum.Enum):
    pending = "pending"
    generated = "generated"
    uploaded = "uploaded"
    approved = "approved"


class FigureSource(str, enum.Enum):
    writing = "writing"
    user_assistant = "user_assistant"
    upload = "upload"


class Figure(Base):
    __tablename__ = "figures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(
        UUID(as_uuid=True),
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_index = Column(Integer, nullable=False, index=True)
    figure_number = Column(String(20))
    figure_type = Column(Enum(FigureType, name="figure_type"), nullable=False)
    status = Column(
        Enum(FigureStatus, name="figure_status"),
        default=FigureStatus.pending,
        nullable=False,
    )

    caption = Column(Text)
    raw_annotation = Column(Text)
    render_source = Column(Text)
    file_path = Column(String(500))
    file_url = Column(String(500))
    svg_url = Column(String(500))

    position_hint = Column(Text)
    sort_order = Column(Integer)

    image_type = Column(String(64))
    subtype = Column(String(64))
    renderer = Column(String(32))
    classification_json = Column(JSONB)
    prompt_spec_json = Column(JSONB)
    figure_source = Column(
        Enum(FigureSource, name="figure_source"),
        default=FigureSource.writing,
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    book = relationship("Book", back_populates="figures")
