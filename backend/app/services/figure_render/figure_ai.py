"""Compatibility wrapper for the Image API figure pipeline.

New code should import from ``app.services.figures.render.image_api``.
"""

from app.services.figures.render.image_api.pipeline import (
    build_figure_prompt,
    generate_figure_image,
    resolve_figure_image_provider,
)
from app.services.figures.render.image_api import STYLE_MAP

__all__ = [
    "STYLE_MAP",
    "build_figure_prompt",
    "generate_figure_image",
    "resolve_figure_image_provider",
]
