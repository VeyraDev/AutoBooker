"""Figure asset storage and resolution."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.binary_asset import AssetDomain, AssetRole, BinaryAsset, FigureAsset, FigureAssetRole
from app.models.figure import Figure
from app.services.assets.binary_asset_service import BinaryAssetService


class FigureAssetService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = BinaryAssetService(db)

    def attach_asset(
        self,
        *,
        figure: Figure,
        content: bytes,
        filename: str,
        mime_type: str,
        owner_user_id: UUID,
        role: FigureAssetRole,
        set_primary_url: bool = False,
    ) -> FigureAsset:
        asset_role = AssetRole.figure_png
        if mime_type == "image/svg+xml" or filename.lower().endswith(".svg"):
            asset_role = AssetRole.figure_svg
        asset = self.assets.create_asset(
            book_id=figure.book_id,
            owner_user_id=owner_user_id,
            content=content,
            filename=filename,
            mime_type=mime_type,
            asset_domain=AssetDomain.figure,
            asset_role=asset_role,
        )
        self.db.query(FigureAsset).filter(
            FigureAsset.figure_id == figure.id,
            FigureAsset.role == role,
            FigureAsset.active.is_(True),
        ).update({"active": False})
        link = FigureAsset(figure_id=figure.id, asset_id=asset.id, role=role, active=True)
        self.db.add(link)
        url = f"/books/{figure.book_id}/assets/{asset.id}/content"
        if set_primary_url or role == FigureAssetRole.primary:
            figure.file_url = url
            figure.file_path = f"db://binary_assets/{asset.id}"
        if role == FigureAssetRole.svg or asset_role == AssetRole.figure_svg:
            figure.svg_url = url
        self.db.flush()
        return link

    def set_primary_asset(
        self,
        *,
        figure: Figure,
        content: bytes,
        filename: str,
        mime_type: str,
        owner_user_id: UUID,
        role: FigureAssetRole,
    ) -> FigureAsset:
        self.db.query(FigureAsset).filter(
            FigureAsset.figure_id == figure.id,
            FigureAsset.role == role,
            FigureAsset.active.is_(True),
        ).update({"active": False})
        return self.attach_asset(
            figure=figure,
            content=content,
            filename=filename,
            mime_type=mime_type,
            owner_user_id=owner_user_id,
            role=role,
            set_primary_url=True,
        )

    @staticmethod
    def _asset_is_svg(asset: BinaryAsset) -> bool:
        return (
            asset.mime_type == "image/svg+xml"
            or asset.asset_role == AssetRole.figure_svg
            or str(asset.filename or "").lower().endswith(".svg")
            or str(asset.extension or "").lower() == "svg"
        )

    def resolve_figure_bytes(self, figure: Figure, *, prefer_svg: bool = False) -> bytes | None:
        links = (
            self.db.query(FigureAsset)
            .filter(FigureAsset.figure_id == figure.id, FigureAsset.active.is_(True))
            .order_by(FigureAsset.created_at.desc())
            .all()
        )
        for link in links:
            asset = self.db.query(BinaryAsset).filter(BinaryAsset.id == link.asset_id).first()
            if not asset:
                continue
            is_svg = self._asset_is_svg(asset)
            if is_svg == prefer_svg:
                return bytes(asset.content)

        if figure.file_path and not str(figure.file_path).startswith("db://"):
            path = Path(figure.file_path)
            if path.is_file():
                is_svg = path.suffix.lower() == ".svg"
                if is_svg == prefer_svg:
                    return path.read_bytes()
        return None
