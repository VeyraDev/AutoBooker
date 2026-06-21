"""旧预置配图模板：结构化示意图、矩阵和双栈结构等。"""

from app.services.figures.render.legacy_svg.figure_templates.matrix_diagram import generate_matrix_diagram
from app.services.figures.render.legacy_svg.figure_templates.structured_diagram import generate_structured_diagram
from app.services.figures.render.legacy_svg.figure_templates.transformer_arch import generate_transformer_architecture

__all__ = [
    "generate_structured_diagram",
    "generate_matrix_diagram",
    "generate_transformer_architecture",
]
