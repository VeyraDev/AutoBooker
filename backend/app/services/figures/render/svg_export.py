"""PNG + SVG 双输出。"""

from __future__ import annotations

from pathlib import Path


def svg_path_for_png(png_path: Path) -> Path:
    return png_path.with_suffix(".svg")


def public_svg_url(book_id, filename_stem: str) -> str:
    return f"/static/figures/{book_id}/{filename_stem}.svg"


def try_export_matplotlib_svg(fig, svg_path: Path) -> bool:
    try:
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
        return svg_path.is_file()
    except Exception:
        return False


def try_export_graphviz_svg(dot_source: str, svg_path: Path) -> bool:
    try:
        import graphviz

        svg_path.parent.mkdir(parents=True, exist_ok=True)
        src = graphviz.Source(dot_source, encoding="utf-8")
        base = svg_path.with_suffix("")
        src.render(str(base), format="svg", cleanup=True)
        rendered = Path(str(base) + ".svg")
        if rendered.is_file() and rendered.resolve() != svg_path.resolve():
            rendered.replace(svg_path)
        return svg_path.is_file()
    except Exception:
        return False
