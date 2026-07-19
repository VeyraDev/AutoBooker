"""共享书架：分类与电子书条目。"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class LibraryItemStatus(str, enum.Enum):
    published = "published"
    pending = "pending"
    archived = "archived"
    rejected = "rejected"


class LibraryCategory(Base):
    __tablename__ = "library_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items = relationship("LibraryItem", back_populates="category")


class LibraryItem(Base):
    """用户上传的共享电子书 / 资料，全站可见。"""

    __tablename__ = "library_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False, index=True)
    authors = Column(JSONB, nullable=True)  # list[str]
    description = Column(Text, nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("library_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    tags = Column(JSONB, nullable=True)  # list[str]
    language = Column(String(32), nullable=True, default="zh")
    file_type = Column(String(16), nullable=False)  # pdf | docx | txt
    filename = Column(String(500), nullable=False)
    mime_type = Column(String(128), nullable=False)
    content = Column(LargeBinary, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    page_count = Column(Integer, nullable=True)
    uploader_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    uploader_name = Column(String(120), nullable=True)
    status = Column(
        Enum(LibraryItemStatus, name="library_item_status"),
        nullable=False,
        default=LibraryItemStatus.published,
        index=True,
    )
    use_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("LibraryCategory", back_populates="items")
