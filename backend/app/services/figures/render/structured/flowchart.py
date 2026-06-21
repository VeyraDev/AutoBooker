"""Graphviz 流程图渲染（含 SVG 双输出）。"""

from __future__ import annotations

from pathlib import Path

from app.services.figures.render.legacy_svg.flowchart import generate_flowchart as _generate_flowchart
from app.services.figures.render.svg_export import try_export_graphviz_svg


def generate_flowchart(
    description: str,
    output_path: Path,
    *,
    model: str,
    book_type: str = "",
    image_type: str = "process_flow",
) -> tuple[str, Path]:
    dot, png = _generate_flowchart(
        description,
        output_path,
        model=model,
        book_type=book_type,
        image_type=image_type,
    )
    if isinstance(dot, str) and dot.strip():
        try_export_graphviz_svg(dot, output_path.with_suffix(".svg"))
    return dot, png
