"""SVG → PNG 导出。"""

from __future__ import annotations

from pathlib import Path


def export_png_from_svg(svg_path: Path, png_path: Path) -> bool:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cairosvg

        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        if png_path.is_file():
            return True
    except Exception:
        pass
    try:
        import fitz

        doc = fitz.open(str(svg_path))
        try:
            if doc.page_count < 1:
                return False
            pix = doc[0].get_pixmap(alpha=False)
            pix.save(str(png_path))
        finally:
            doc.close()
        return png_path.is_file()
    except Exception:
        return False
