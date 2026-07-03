import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class OptimizationStatus(str, enum.Enum):
    parsing = "parsing"
    mapping_review = "mapping_review"
    ready_for_analysis = "ready_for_analysis"
    analyzing = "analyzing"
    plan_ready = "plan_ready"
    optimizing = "optimizing"
    editing = "editing"
    completed = "completed"
    failed = "failed"


class OptimizationProject(Base):
    __tablename__ = "optimization_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, unique=True)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("reference_files.id", ondelete="RESTRICT"), nullable=False)
    status = Column(Enum(OptimizationStatus, name="optimization_status"), nullable=False, default=OptimizationStatus.parsing)
    allow_structure_changes = Column(Boolean, nullable=False, default=False, server_default="false")
    optimization_goals = Column(JSONB, nullable=True)
    diagnosis = Column(JSONB, nullable=True)
    optimization_plan = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    baseline_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ManuscriptBaselineChapter(Base):
    __tablename__ = "manuscript_baseline_chapters"
    __table_args__ = (UniqueConstraint("project_id", "original_index", name="uq_baseline_project_index"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    original_index = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    heading_level = Column(Integer, nullable=False, default=1)
    body_text = Column(Text, nullable=False, default="")
    source_locator = Column(JSONB, nullable=True)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ManuscriptChapterMapping(Base):
    __tablename__ = "manuscript_chapter_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_chapter_id = Column(UUID(as_uuid=True), ForeignKey("manuscript_baseline_chapters.id", ondelete="CASCADE"), nullable=False, unique=True)
    working_chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    outline_chapter_index = Column(Integer, nullable=True)
    outline_title = Column(String(500), nullable=True)
    confidence = Column(Integer, nullable=False, default=100)
    status = Column(String(32), nullable=False, default="auto_confirmed")
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ManuscriptRevision(Base):
    __tablename__ = "manuscript_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_chapter_id = Column(UUID(as_uuid=True), ForeignKey("manuscript_baseline_chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_revision_id = Column(UUID(as_uuid=True), ForeignKey("manuscript_revisions.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(32), nullable=False, default="ai_optimization")
    body_text = Column(Text, nullable=False)
    tiptap_json = Column(JSONB, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="proposed")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)


class OptimizationJob(Base):
    __tablename__ = "optimization_jobs"
    __table_args__ = (
        Index(
            "uq_optimization_jobs_active_project",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    current_chapter_index = Column(Integer, nullable=True)
    progress_pct = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
