"""Unified asset resolution: DB first, local disk fallback."""

from __future__ import annotations

import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.binary_asset import BinaryAsset, FigureAsset
from app.models.figure import Figure
from app.services.assets.figure_asset_service import FigureAssetService
from app.services.figures.storage.manager import figure_storage

_DB_ASSET_RE = re.compile(r"db://binary_assets/([0-9a-f-]+)", re.I)
_API_ASSET_RE = re.compile(r"/books/([0-9a-f-]+)/assets/([0-9a-f-]+)/content", re.I)


def _new_temp_path(*, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        return Path(tmp.name)


def _write_temp_bytes(content: bytes, *, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        return Path(tmp.name)


class AssetResolver:
    def __init__(self, db: Session):
        self.db = db
        self._figure_assets = FigureAssetService(db)

    @staticmethod
    def asset_content_url(book_id: UUID, asset_id: UUID) -> str:
        return f"/api/books/{book_id}/assets/{asset_id}/content"

    def parse_asset_id_from_figure(self, fig: Figure) -> UUID | None:
        raw = str(fig.file_path or fig.file_url or "")
        m = _DB_ASSET_RE.search(raw)
        if m:
            try:
                return UUID(m.group(1))
            except ValueError:
                pass
        m = _API_ASSET_RE.search(raw)
        if m:
            try:
                return UUID(m.group(2))
            except ValueError:
                pass
        link = (
            self.db.query(FigureAsset)
            .filter(FigureAsset.figure_id == fig.id, FigureAsset.active.is_(True))
            .order_by(FigureAsset.created_at.desc())
            .first()
        )
        return link.asset_id if link else None

    def sync_figure_urls_from_assets(self, fig: Figure) -> None:
        asset_id = self.parse_asset_id_from_figure(fig)
        if asset_id:
            url = self.asset_content_url(fig.book_id, asset_id)
            fig.file_url = url
            fig.file_path = f"db://binary_assets/{asset_id}"
            svg_link = (
                self.db.query(FigureAsset)
                .filter(
                    FigureAsset.figure_id == fig.id,
                    FigureAsset.active.is_(True),
                )
                .join(BinaryAsset, BinaryAsset.id == FigureAsset.asset_id)
                .filter(BinaryAsset.mime_type == "image/svg+xml")
                .first()
            )
            if svg_link:
                fig.svg_url = self.asset_content_url(fig.book_id, svg_link.asset_id)
            return
        from app.services.figures.generation import sync_figure_urls_from_disk

        sync_figure_urls_from_disk(fig, chapter_index=fig.chapter_index)

    def resolve_figure_bytes(self, fig: Figure, *, prefer_svg: bool = False) -> bytes | None:
        return self._figure_assets.resolve_figure_bytes(fig, prefer_svg=prefer_svg)

    def resolve_local_path(self, url_or_path: str) -> Path | None:
        raw = str(url_or_path or "").strip()
        if not raw:
            return None
        m = _DB_ASSET_RE.search(raw)
        if m:
            return self._materialize_asset_bytes(UUID(m.group(1)), suffix=".bin")
        m = _API_ASSET_RE.search(raw)
        if m:
            return self._materialize_asset_bytes(UUID(m.group(2)), suffix=".bin")
        return figure_storage.resolve_local_path(raw)

    @contextmanager
    def materialize_local_path(self, url_or_path: str) -> Iterator[Path | None]:
        raw = str(url_or_path or "").strip()
        tmp_path: Path | None = None
        try:
            if not raw:
                yield None
                return
            m = _DB_ASSET_RE.search(raw)
            if m:
                tmp_path = self._materialize_asset_bytes(UUID(m.group(1)), suffix=".bin")
                yield tmp_path
                return
            m = _API_ASSET_RE.search(raw)
            if m:
                tmp_path = self._materialize_asset_bytes(UUID(m.group(2)), suffix=".bin")
                yield tmp_path
                return
            yield figure_storage.resolve_local_path(raw)
        finally:
            if tmp_path:
                tmp_path.unlink(missing_ok=True)

    def _materialize_asset_bytes(self, asset_id: UUID, *, suffix: str) -> Path | None:
        asset = self.db.query(BinaryAsset).filter(BinaryAsset.id == asset_id).first()
        if not asset:
            return None
        ext = suffix
        if asset.extension:
            ext = f".{asset.extension}"
        elif asset.mime_type == "image/png":
            ext = ".png"
        elif asset.mime_type == "image/svg+xml":
            ext = ".svg"
        return _write_temp_bytes(bytes(asset.content), suffix=ext)

    @contextmanager
    def materialize_figure_raster(self, fig: Figure) -> Iterator[Path | None]:
        """Yield a local path suitable for DOCX/PDF embed (PNG preferred)."""
        png_bytes = self.resolve_figure_bytes(fig, prefer_svg=False)
        svg_bytes = self.resolve_figure_bytes(fig, prefer_svg=True)
        tmp_paths: list[Path] = []
        try:
            if png_bytes:
                p = _write_temp_bytes(png_bytes, suffix=".png")
                tmp_paths.append(p)
                yield p
                return
            if svg_bytes:
                svg_path = _write_temp_bytes(svg_bytes, suffix=".svg")
                tmp_paths.append(svg_path)
                from app.services.figures.render.svg.export_png import export_png_from_svg

                png_path = _new_temp_path(suffix=".png")
                tmp_paths.append(png_path)
                if export_png_from_svg(svg_path, png_path) and png_path.is_file():
                    yield png_path
                    return
            from app.services.figures.export_assets import find_figure_asset_on_disk

            for path in find_figure_asset_on_disk(fig.book_id, fig.id):
                if path.suffix.lower() == ".png":
                    yield path
                    return
                if path.suffix.lower() == ".svg":
                    from app.services.figures.render.svg.export_png import export_png_from_svg

                    png_path = _new_temp_path(suffix=".png")
                    tmp_paths.append(png_path)
                    if export_png_from_svg(path, png_path) and png_path.is_file():
                        yield png_path
                        return
            canonical = figure_storage.png_path(fig.book_id, fig.chapter_index, fig.id)
            if canonical.is_file():
                yield canonical
                return
            yield None
        finally:
            for p in tmp_paths:
                p.unlink(missing_ok=True)

    @contextmanager
    def materialize_figure_local_path_from_attrs(self, attrs: dict) -> Iterator[Path | None]:
        figure_id = str(attrs.get("figureId") or attrs.get("figure_id") or "").strip()
        book_id = str(attrs.get("book_id") or attrs.get("bookId") or "").strip()
        if figure_id and book_id:
            try:
                fig = (
                    self.db.query(Figure)
                    .filter(Figure.id == UUID(figure_id), Figure.book_id == UUID(book_id))
                    .first()
                )
                if fig:
                    with self.materialize_figure_raster(fig) as path:
                        if path and path.is_file():
                            yield path
                            return
            except ValueError:
                pass
        for key in ("fileUrl", "file_url", "svgUrl", "svg_url", "file_path"):
            raw = str(attrs.get(key) or "").strip()
            if raw:
                with self.materialize_local_path(raw) as local:
                    if local and local.is_file():
                        yield local
                        return
        yield None

    def resolve_figure_local_path_from_attrs(self, attrs: dict) -> Path | None:
        figure_id = str(attrs.get("figureId") or attrs.get("figure_id") or "").strip()
        book_id = str(attrs.get("book_id") or attrs.get("bookId") or "").strip()
        if figure_id and book_id:
            try:
                fig = (
                    self.db.query(Figure)
                    .filter(Figure.id == UUID(figure_id), Figure.book_id == UUID(book_id))
                    .first()
                )
                if fig:
                    with self.materialize_figure_raster(fig) as path:
                        if path and path.is_file():
                            return _write_temp_bytes(path.read_bytes(), suffix=path.suffix or ".png")
            except ValueError:
                pass
        for key in ("fileUrl", "file_url", "svgUrl", "svg_url", "file_path"):
            raw = str(attrs.get(key) or "").strip()
            if raw:
                local = self.resolve_local_path(raw)
                if local and local.is_file():
                    return local
        return None
