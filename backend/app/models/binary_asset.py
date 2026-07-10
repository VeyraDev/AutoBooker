"""Binary asset storage in PostgreSQL."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class AssetDomain(str, enum.Enum):
    reference = "reference"
    figure = "figure"
    export_temp = "export_temp"
    misc = "misc"


class AssetRole(str, enum.Enum):
    original_upload = "original_upload"
    figure_png = "figure_png"
    figure_svg = "figure_svg"
    source = "source"
    thumbnail = "thumbnail"
    export_png = "export_png"


class BinaryAsset(Base):
    __tablename__ = "binary_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_domain = Column(Enum(AssetDomain, name="asset_domain"), nullable=False)
    asset_role = Column(Enum(AssetRole, name="asset_role"), nullable=False)
    filename = Column(String(500), nullable=False)
    mime_type = Column(String(128), nullable=False)
    extension = Column(String(32), nullable=True)
    content = Column(LargeBinary, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class FigureAssetRole(str, enum.Enum):
    primary = "primary"
    png = "png"
    svg = "svg"
    source = "source"
    thumbnail = "thumbnail"
    export_png = "export_png"


class FigureAsset(Base):
    __tablename__ = "figure_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    figure_id = Column(UUID(as_uuid=True), ForeignKey("figures.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("binary_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(FigureAssetRole, name="figure_asset_role"), nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
