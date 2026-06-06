"""SVG → PNG 导出。"""

from __future__ import annotations

from pathlib import Path


def export_png_from_svg(svg_path: Path, png_path: Path) -> bool:
    try:
        import cairosvg

        png_path.parent.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        return png_path.is_file()
    except Exception:
        pass
    try:
        from PIL import Image
        import io

        # 无 cairosvg 时仅保留 SVG
        return False
    except Exception:
        return False
