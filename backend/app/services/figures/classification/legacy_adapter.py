"""旧 image_type / renderer 兼容。"""

from __future__ import annotations

from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_STRUCTURED_CHART,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_RAG,
    RENDERER_STRUCTURED_SWOT,
    RENDERER_STRUCTURED_TRANSFORMER,
)

_LEGACY_RENDERER_MAP = {
    "structured_template": RENDERER_STRUCTURED_GENERIC,
    "decision_tree_template": RENDERER_STRUCTURED_GENERIC,
    "matrix_template": RENDERER_STRUCTURED_MATRIX,
    "transformer_template": RENDERER_STRUCTURED_TRANSFORMER,
    "graphviz": RENDERER_STRUCTURED_FLOWCHART,
    "mermaid": RENDERER_STRUCTURED_FLOWCHART,
    "matplotlib": RENDERER_STRUCTURED_CHART,
    "image_api": RENDERER_ILLUSTRATION,
}


def normalize_renderer_key(renderer: str | None) -> str:
    r = (renderer or "").strip().lower()
    if r in _LEGACY_RENDERER_MAP:
        return _LEGACY_RENDERER_MAP[r]
    if r.startswith("structured.") or r.startswith("illustration."):
        return r
    return r or RENDERER_STRUCTURED_GENERIC
