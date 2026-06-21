"""旧 image_type / renderer 兼容。"""

from __future__ import annotations

from app.services.figures.intent.taxonomy import (
    RENDERER_GENERIC_COMPOSITOR,
    RENDERER_ILLUSTRATION,
    RENDERER_STRUCTURED_CHART,
    RENDERER_STRUCTURED_DUAL_STACK,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_THREE_COLUMN,
    RENDERER_STRUCTURED_SWOT,
)

_LEGACY_RENDERER_MAP = {
    "structured_template": RENDERER_STRUCTURED_GENERIC,
    "decision_tree_template": RENDERER_STRUCTURED_GENERIC,
    "matrix_template": RENDERER_STRUCTURED_MATRIX,
    "transformer_template": RENDERER_STRUCTURED_DUAL_STACK,
    "graphviz": RENDERER_STRUCTURED_FLOWCHART,
    "mermaid": RENDERER_STRUCTURED_FLOWCHART,
    "matplotlib": RENDERER_STRUCTURED_CHART,
    "image_api": RENDERER_ILLUSTRATION,
    "compositor": RENDERER_GENERIC_COMPOSITOR,
    "generic.compositor": RENDERER_GENERIC_COMPOSITOR,
    "structured." + "transformer": RENDERER_STRUCTURED_DUAL_STACK,
    "structured." + "rag": RENDERER_STRUCTURED_THREE_COLUMN,
}


def normalize_renderer_key(renderer: str | None) -> str:
    r = (renderer or "").strip().lower()
    if r in _LEGACY_RENDERER_MAP:
        return _LEGACY_RENDERER_MAP[r]
    if r.startswith("structured.") or r.startswith("illustration.") or r.startswith("generic."):
        return r
    return r or RENDERER_STRUCTURED_GENERIC
