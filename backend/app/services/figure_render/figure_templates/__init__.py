"""预置配图模板：结构化示意图、矩阵、Transformer 等。"""

from app.services.figure_render.figure_templates.matrix_diagram import generate_matrix_diagram
from app.services.figure_render.figure_templates.structured_diagram import generate_structured_diagram
from app.services.figure_render.figure_templates.transformer_arch import generate_transformer_architecture

__all__ = [
    "generate_structured_diagram",
    "generate_matrix_diagram",
    "generate_transformer_architecture",
]
