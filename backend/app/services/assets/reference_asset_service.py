"""Reference file asset helpers."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.binary_asset import AssetDomain, AssetRole, BinaryAsset
from app.models.reference import ReferenceFile
from app.services.assets.binary_asset_service import BinaryAssetService
from app.services.assets.temporary_workspace import TemporaryWorkspace


class ReferenceAssetService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = BinaryAssetService(db)

    def attach_upload(
        self,
        *,
        ref: ReferenceFile,
        content: bytes,
        owner_user_id: UUID,
    ) -> ReferenceFile:
        asset = self.assets.create_asset(
            book_id=ref.book_id,
            owner_user_id=owner_user_id,
            content=content,
            filename=ref.filename,
            mime_type=None,
            asset_domain=AssetDomain.reference,
            asset_role=AssetRole.original_upload,
        )
        ref.asset_id = asset.id
        ref.storage_path = f"db://binary_assets/{asset.id}"
        return ref

    def _asset_for_ref(self, ref: ReferenceFile) -> BinaryAsset | None:
        if not ref.asset_id:
            return None
        return self.db.query(BinaryAsset).filter(BinaryAsset.id == ref.asset_id).first()

    @staticmethod
    def _suffix_for(ref: ReferenceFile, asset: BinaryAsset | None = None) -> str:
        if asset and asset.extension:
            return f".{asset.extension}"
        file_type = str(ref.file_type or "").strip().lower().lstrip(".")
        return f".{file_type or 'bin'}"

    @contextmanager
    def materialize(self, ref: ReferenceFile) -> Iterator[Path]:
        """Yield a local path for code that still needs filesystem access.

        DB-backed assets are written to a request-scoped temp file and removed
        after use. Legacy local paths are yielded as-is and are not deleted.
        """
        asset = self._asset_for_ref(ref)
        if asset:
            with TemporaryWorkspace().materialize(bytes(asset.content), self._suffix_for(ref, asset)) as path:
                yield path
            return

        raw_path = str(ref.storage_path or "").strip()
        if raw_path and not raw_path.startswith("db://"):
            path = Path(raw_path)
            if path.is_file():
                yield path
                return
        raise RuntimeError("Reference file has no readable content")

    def materialize_to_temp_path(self, ref: ReferenceFile) -> Path:
        """Compatibility helper: caller owns cleanup for DB-backed temp files."""
        asset = self._asset_for_ref(ref)
        if asset:
            with tempfile.NamedTemporaryFile(suffix=self._suffix_for(ref, asset), delete=False) as tmp:
                tmp.write(bytes(asset.content))
                return Path(tmp.name)
        if ref.storage_path and not str(ref.storage_path).startswith("db://"):
            return Path(ref.storage_path)
        raise RuntimeError("Reference file has no readable content")
