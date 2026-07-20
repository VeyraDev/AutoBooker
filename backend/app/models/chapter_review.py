import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ChapterReview(Base):
    __tablename__ = "chapter_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    manuscript_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_hash = Column(String(80), nullable=False, index=True)
    snapshot_version = Column(Integer, default=1, nullable=False)
    markdown_snapshot = Column(Text, nullable=False)
    total_score = Column(Integer, default=0, nullable=False)
    dimensions = Column(JSONB, nullable=False, default=list)
    weights = Column(JSONB, nullable=False, default=dict)
    score_schema_version = Column(String(32), default="review_v2", nullable=False)
    prompt_version = Column(String(32), default="review_agent_v2", nullable=False)
    model_name = Column(String(120))
    constitution_hash = Column(String(80))
    citation_index_hash = Column(String(80))
    figure_index_hash = Column(String(80))
    status = Column(String(32), default="completed", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    issues = relationship(
        "ChapterReviewIssue",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="ChapterReviewIssue.created_at",
    )


class ChapterReviewIssue(Base):
    __tablename__ = "chapter_review_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id = Column(UUID(as_uuid=True), ForeignKey("chapter_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_hash = Column(String(80), nullable=False, index=True)
    dimension = Column(String(64), nullable=False, index=True)
    issue_type = Column(String(80), nullable=False, index=True)
    severity = Column(String(32), default="medium", nullable=False, index=True)
    penalty = Column(Integer, default=0, nullable=False)
    status = Column(String(24), default="open", nullable=False, index=True)
    title = Column(String(240), nullable=False, default="")
    explanation = Column(Text, default="")
    quote = Column(Text, default="")
    action = Column(String(24), default="revise", nullable=False)
    replacement_text = Column(Text, default="")
    paragraph_id = Column(String(80), index=True)
    paragraph_index = Column(Integer)
    char_start = Column(Integer)
    char_end = Column(Integer)
    anchor_hash = Column(String(80), index=True)
    issue_fingerprint = Column(String(120), index=True)
    quality_evidence = Column(JSONB, nullable=True)
    detector = Column(String(80), default="review_agent", nullable=False)
    confidence = Column(Numeric(4, 3), default=0.7, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    applied_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    dismissed_at = Column(DateTime(timezone=True))

    review = relationship("ChapterReview", back_populates="issues")


class ReviewApplication(Base):
    __tablename__ = "review_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id = Column(UUID(as_uuid=True), ForeignKey("chapter_review_issues.id", ondelete="SET NULL"), nullable=True, index=True)
    review_id = Column(UUID(as_uuid=True), ForeignKey("chapter_reviews.id", ondelete="SET NULL"), nullable=True, index=True)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    before_hash = Column(String(80), nullable=False)
    after_hash = Column(String(80), nullable=False)
    apply_type = Column(String(32), nullable=False)
    locator_strategy = Column(String(64), default="")
    locator_confidence = Column(Numeric(4, 3), default=0.0, nullable=False)
    diff = Column(JSONB, nullable=False, default=dict)
    affected_dimensions = Column(JSONB, nullable=False, default=list)
    score_before = Column(JSONB, nullable=True)
    score_after = Column(JSONB, nullable=True)
    warning = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
