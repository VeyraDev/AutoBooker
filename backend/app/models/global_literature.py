"""公共经典文献库。"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class GlobalLiteratureSource(str, enum.Enum):
    curated = "curated"
    community = "community"


class GlobalLiteratureStatus(str, enum.Enum):
    approved = "approved"
    pending = "pending"
    rejected = "rejected"


class GlobalLiterature(Base):
    __tablename__ = "global_literature"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(Enum(GlobalLiteratureSource, name="global_literature_source"), nullable=False)
    status = Column(
        Enum(GlobalLiteratureStatus, name="global_literature_status"),
        nullable=False,
        default=GlobalLiteratureStatus.approved,
    )
    title = Column(String(500), nullable=False)
    authors = Column(JSONB, nullable=True)
    year = Column(Integer, nullable=True)
    journal = Column(String(300), nullable=True)
    doi = Column(String(200), nullable=True)
    url = Column(String(1000), nullable=True)
    abstract = Column(Text, nullable=True)
    tags = Column(JSONB, nullable=True)
    contributor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    contributor_name = Column(String(120), nullable=True)
    cite_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
