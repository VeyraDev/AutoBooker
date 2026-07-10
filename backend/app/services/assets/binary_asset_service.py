"""Binary asset CRUD service."""

from __future__ import annotations

import hashlib
import mimetypes
from io import BytesIO
from uuid import UUID

from fastapi import HTTPException, status
from PIL import Image
from sqlalchemy.orm import Session

from app.models.binary_asset import AssetDomain, AssetRole, BinaryAsset


def _image_dimensions(content: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if not mime_type.startswith("image/"):
        return None, None
    try:
        with Image.open(BytesIO(content)) as img:
            return img.size
    except Exception:
        return None, None


class BinaryAssetService:
    def __init__(self, db: Session):
        self.db = db

    def create_asset(
        self,
        *,
        book_id: UUID,
        owner_user_id: UUID,
        content: bytes,
        filename: str,
        mime_type: str | None,
        asset_domain: AssetDomain,
        asset_role: AssetRole,
        metadata: dict | None = None,
    ) -> BinaryAsset:
        mime = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        sha256 = hashlib.sha256(content).hexdigest()
        width, height = _image_dimensions(content, mime)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else None
        asset = BinaryAsset(
            book_id=book_id,
            owner_user_id=owner_user_id,
            asset_domain=asset_domain,
            asset_role=asset_role,
            filename=filename,
            mime_type=mime,
            extension=ext,
            content=content,
            size_bytes=len(content),
            sha256=sha256,
            width=width,
            height=height,
            metadata_json=metadata,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def get_asset_for_book(self, *, book_id: UUID, asset_id: UUID) -> BinaryAsset:
        asset = (
            self.db.query(BinaryAsset)
            .filter(BinaryAsset.id == asset_id, BinaryAsset.book_id == book_id, BinaryAsset.deleted_at.is_(None))
            .first()
        )
        if not asset:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
        return asset

    def stream_asset(self, *, book_id: UUID, asset_id: UUID) -> tuple[bytes, str, str]:
        asset = self.get_asset_for_book(book_id=book_id, asset_id=asset_id)
        return bytes(asset.content), asset.mime_type, asset.filename

    def soft_delete_asset(self, *, book_id: UUID, asset_id: UUID) -> None:
        from datetime import datetime, timezone

        asset = self.get_asset_for_book(book_id=book_id, asset_id=asset_id)
        asset.deleted_at = datetime.now(timezone.utc)
