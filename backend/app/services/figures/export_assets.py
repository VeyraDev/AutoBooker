"""导出前确保配图可被 DOCX/PDF 嵌入（SVG → PNG 等）。"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.models.figure import Figure
from app.services.figures.render.svg.export_png import export_png_from_svg
from app.services.figures.storage.manager import figure_storage


def find_figure_asset_on_disk(book_id: UUID, figure_id: UUID) -> list[Path]:
    """在规范目录或全书范围内查找 figure.png / figure.svg。"""
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


def ensure_figure_png_for_export(
    book_id: UUID,
    chapter_index: int,
    figure_id: UUID,
) -> Path | None:
    """确保存在可嵌入 DOCX 的 PNG；返回最佳位图路径。"""
    png_path = figure_storage.png_path(book_id, chapter_index, figure_id)
    if png_path.is_file():
        return png_path

    svg_path = figure_storage.svg_path(book_id, chapter_index, figure_id)
    if not svg_path.is_file():
        for path in find_figure_asset_on_disk(book_id, figure_id):
            if path.suffix.lower() == ".png":
                return path
            svg_path = path
        if not svg_path.is_file():
            return None

    if export_png_from_svg(svg_path, png_path) and png_path.is_file():
        return png_path

    cache_png = svg_path.parent / ".export-cache.png"
    if export_png_from_svg(svg_path, cache_png) and cache_png.is_file():
        return cache_png
    return None


def prepare_figure_for_export(fig: Figure) -> Path | None:
    """单张图导出前预处理。"""
    return ensure_figure_png_for_export(fig.book_id, fig.chapter_index, fig.id)


def prepare_book_figures_for_export(figures: list[Figure]) -> None:
    """全书导出前批量确保 PNG 副本存在。"""
    for fig in figures:
        prepare_figure_for_export(fig)
