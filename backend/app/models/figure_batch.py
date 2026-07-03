import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class FigureBatchRun(Base):
    __tablename__ = "figure_batch_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_index = Column(Integer, nullable=True)
    trigger = Column(String(24), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="pending")
    total = Column(Integer, nullable=False, default=0)
    completed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class FigureBatchItem(Base):
    __tablename__ = "figure_batch_items"
    __table_args__ = (
        UniqueConstraint("run_id", "figure_id", name="uq_figure_batch_run_figure"),
        Index(
            "uq_figure_batch_active_figure",
            "figure_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("figure_batch_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    figure_id = Column(UUID(as_uuid=True), ForeignKey("figures.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
