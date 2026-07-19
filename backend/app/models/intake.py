"""Project intake models for unified input flow."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


from app.models.book import CreationOrigin


class IntakeStatus(str, enum.Enum):
    collecting = "collecting"
    understanding_ready = "understanding_ready"
    confirmed = "confirmed"
    superseded = "superseded"


class IntakeItemType(str, enum.Enum):
    natural_text = "natural_text"
    pasted_text = "pasted_text"
    upload = "upload"


class IntakeItemStatus(str, enum.Enum):
    pending = "pending"
    parsed = "parsed"
    failed = "failed"
    disabled = "disabled"


class UnderstandingStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    superseded = "superseded"


class WritingPlanStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    superseded = "superseded"


class ProjectIntake(Base):
    __tablename__ = "project_intakes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    creation_origin = Column(Enum(CreationOrigin, name="creation_origin"), nullable=False)
    status = Column(Enum(IntakeStatus, name="intake_status"), nullable=False, default=IntakeStatus.collecting)
    raw_goal_text = Column(Text, nullable=True)
    negative_constraints_text = Column(Text, nullable=True)
    confirmed_understanding_id = Column(UUID(as_uuid=True), nullable=True)
    confirmed_writing_plan_id = Column(UUID(as_uuid=True), nullable=True)
    confirmed_writing_basis_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class IntakeItem(Base):
    __tablename__ = "intake_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intake_id = Column(UUID(as_uuid=True), ForeignKey("project_intakes.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(Enum(IntakeItemType, name="intake_item_type"), nullable=False)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("binary_assets.id", ondelete="SET NULL"), nullable=True)
    reference_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reference_files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    text_content = Column(Text, nullable=True)
    filename = Column(String(500), nullable=True)
    parsed_preview = Column(Text, nullable=True)
    detected_roles = Column(JSONB, nullable=True)
    source_url = Column(String(2000), nullable=True)
    source_type = Column(String(64), nullable=True)
    provider = Column(String(64), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=True)
    source_metadata = Column(JSONB, nullable=True)
    status = Column(Enum(IntakeItemStatus, name="intake_item_status"), nullable=False, default=IntakeItemStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InputUnderstanding(Base):
    __tablename__ = "input_understandings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    intake_id = Column(UUID(as_uuid=True), ForeignKey("project_intakes.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    summary_json = Column(JSONB, nullable=True)
    user_facing_text = Column(Text, nullable=True)
    evidence_refs = Column(JSONB, nullable=True)
    preserve_rules = Column(JSONB, nullable=True)
    editable_rules = Column(JSONB, nullable=True)
    avoid_rules = Column(JSONB, nullable=True)
    unclear_questions = Column(JSONB, nullable=True)
    status = Column(Enum(UnderstandingStatus, name="understanding_status"), nullable=False, default=UnderstandingStatus.draft)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WritingPlan(Base):
    __tablename__ = "writing_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    intake_id = Column(UUID(as_uuid=True), ForeignKey("project_intakes.id", ondelete="CASCADE"), nullable=False)
    understanding_id = Column(UUID(as_uuid=True), ForeignKey("input_understandings.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    plan_json = Column(JSONB, nullable=True)
    user_facing_text = Column(Text, nullable=True)
    impact_map = Column(JSONB, nullable=True)
    status = Column(Enum(WritingPlanStatus, name="writing_plan_status"), nullable=False, default=WritingPlanStatus.draft)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
