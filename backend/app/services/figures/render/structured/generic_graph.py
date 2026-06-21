"""结构化 generic_graph 渲染（迁移自 figure_templates）。"""

from app.services.figures.render.legacy_svg.figure_templates.structured_diagram import (
    generate_structured_diagram,
    render_structured_diagram,
)

__all__ = ["generate_structured_diagram", "render_structured_diagram"]
