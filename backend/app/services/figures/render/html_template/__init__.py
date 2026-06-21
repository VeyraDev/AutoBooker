"""Template-based infographic renderer.

This module implements the new route described by ``infographic_renderer_mvp``:

natural-language request -> DiagramSpec -> validator/normalizer -> template SVG
-> PNG.

It is intentionally independent from the legacy GraphIR/SVG renderer and from
the Image API route.
"""

from app.services.figures.render.html_template.compiler import compile_diagram_spec
from app.services.figures.render.html_template.renderer import render_infographic_spec
from app.services.figures.render.html_template.schema import (
    INFOGRAPHIC_TEMPLATE_SUBTYPES,
    STYLE_PROFILE,
    TEMPLATE_IDS,
    TEMPLATE_LIMITS,
    supports_infographic_template,
)
from app.services.figures.render.html_template.validator import validate_and_normalize

__all__ = [
    "INFOGRAPHIC_TEMPLATE_SUBTYPES",
    "STYLE_PROFILE",
    "TEMPLATE_IDS",
    "TEMPLATE_LIMITS",
    "compile_diagram_spec",
    "render_infographic_spec",
    "supports_infographic_template",
    "validate_and_normalize",
]
