"""Project-level review rule confirmations."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class ReviewRuleOverride(Base):
    __tablename__ = "review_rule_overrides"
    __table_args__ = (
        UniqueConstraint("book_id", "candidate_id", "version", name="uq_review_rule_override_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(300), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(24), nullable=False, default="active", index=True)
    recommendation = Column(String(24), nullable=False, default="")
    product_dimension = Column(String(80), nullable=False, default="unknown")
    issue_type = Column(String(120), nullable=False, default="review_issue")
    fix_capability = Column(String(80), nullable=False, default="")
    detector = Column(String(120), nullable=False, default="")
    rule_text = Column(Text, nullable=False, default="")
    decision_note = Column(Text, nullable=True)
    source_stats_json = Column(JSONB, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
