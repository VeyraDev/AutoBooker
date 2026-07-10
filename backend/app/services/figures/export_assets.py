"""导出前确保配图可被 DOCX/PDF 嵌入（DB 优先，本地 fallback）。"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.figure import Figure
from app.services.assets.asset_resolver import AssetResolver
from app.services.figures.storage.manager import figure_storage


def find_figure_asset_on_disk(book_id: UUID, figure_id: UUID) -> list[Path]:
    """在规范目录或全书范围内查找 figure.png / figure.svg（fallback）。"""
    found: list[Path] = []
    book_root = figure_storage.legacy_dir(book_id)
    if not book_root.is_dir():
        return found

    figure_key = str(figure_id)
    for chapter_dir in book_root.iterdir():
        if not chapter_dir.is_dir():
            continue
        asset_dir = chapter_dir / figure_key
        if not asset_dir.is_dir():
            continue
        for name in ("figure.png", "figure.svg"):
            path = asset_dir / name
            if path.is_file():
                found.append(path)

    legacy_png = book_root / f"{figure_id.hex}.png"
    legacy_svg = book_root / f"{figure_id.hex}.svg"
    if legacy_png.is_file():
        found.append(legacy_png)
    if legacy_svg.is_file():
        found.append(legacy_svg)
    return found


def prepare_figure_for_export(fig: Figure, db: Session) -> None:
    """单张图导出前同步 DB 资产 URL。"""
    AssetResolver(db).sync_figure_urls_from_assets(fig)


def prepare_book_figures_for_export(figures: list[Figure], db: Session) -> None:
    """全书导出前批量同步配图 URL。"""
    resolver = AssetResolver(db)
    for fig in figures:
        resolver.sync_figure_urls_from_assets(fig)
