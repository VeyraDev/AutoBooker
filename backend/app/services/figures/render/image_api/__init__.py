"""Image API figure rendering pipeline."""

from app.services.figures.render.image_api.pipeline import (
    build_figure_prompt,
    generate_figure_image,
    resolve_figure_image_provider,
)

STYLE_MAP = {
    "default": "专业出版插图风格",
    "professional": "专业出版插图风格",
    "academic": "学术出版插图风格",
    "minimal": "简洁现代插图风格",
}

__all__ = [
    "STYLE_MAP",
    "build_figure_prompt",
    "generate_figure_image",
    "resolve_figure_image_provider",
]
