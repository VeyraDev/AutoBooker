"""Diagram family / subtype 与 renderer 映射。"""

from __future__ import annotations

# Renderer 键（单一真相）
RENDERER_STRUCTURED_GENERIC = "structured.generic_graph"
RENDERER_STRUCTURED_TRANSFORMER = "structured.transformer"
RENDERER_STRUCTURED_RAG = "structured.rag"
RENDERER_STRUCTURED_SWOT = "structured.swot"
RENDERER_STRUCTURED_MATRIX = "structured.matrix"
RENDERER_STRUCTURED_FLOWCHART = "structured.flowchart"
RENDERER_STRUCTURED_CHART = "structured.chart"
RENDERER_ILLUSTRATION = "illustration.image_api"
RENDERER_NEED_DATA = "need_data"
RENDERER_UPLOAD = "upload"

STRUCTURED_RENDERERS = frozenset({
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_TRANSFORMER,
    RENDERER_STRUCTURED_RAG,
    RENDERER_STRUCTURED_SWOT,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_CHART,
})

SUBTYPE_TO_RENDERER: dict[str, str] = {
    "decision_tree": RENDERER_STRUCTURED_GENERIC,
    "decision_flow": RENDERER_STRUCTURED_GENERIC,
    "transformer": RENDERER_STRUCTURED_TRANSFORMER,
    "rag": RENDERER_STRUCTURED_RAG,
    "agent": RENDERER_STRUCTURED_RAG,
    "swot": RENDERER_STRUCTURED_SWOT,
    "comparison_matrix": RENDERER_STRUCTURED_SWOT,
    "quadrant_matrix": RENDERER_STRUCTURED_SWOT,
    "attention_matrix": RENDERER_STRUCTURED_MATRIX,
    "process_flow": RENDERER_STRUCTURED_FLOWCHART,
    "business_workflow": RENDERER_STRUCTURED_FLOWCHART,
    "system_architecture": RENDERER_STRUCTURED_FLOWCHART,
    "microservice_architecture": RENDERER_STRUCTURED_FLOWCHART,
    "chart": RENDERER_STRUCTURED_CHART,
    "mindmap": RENDERER_STRUCTURED_GENERIC,
    "taxonomy_map": RENDERER_STRUCTURED_GENERIC,
    "knowledge_graph": RENDERER_STRUCTURED_GENERIC,
    "timeline": RENDERER_STRUCTURED_GENERIC,
    "roadmap": RENDERER_STRUCTURED_GENERIC,
    "org_chart": RENDERER_STRUCTURED_GENERIC,
    "hierarchy_chart": RENDERER_STRUCTURED_GENERIC,
    "scene_illustration": RENDERER_ILLUSTRATION,
    "infographic": RENDERER_ILLUSTRATION,
    "concept_illustration": RENDERER_ILLUSTRATION,
    "chapter_summary": RENDERER_ILLUSTRATION,
}

FAMILY_DEFAULT_SUBTYPE: dict[str, str] = {
    "architecture": "system_architecture",
    "decision": "decision_tree",
    "workflow": "process_flow",
    "matrix": "comparison_matrix",
    "knowledge": "mindmap",
    "timeline": "timeline",
    "organization": "org_chart",
    "illustration": "concept_illustration",
    "data": "chart",
}

# 兼容旧 image_type 字段
SUBTYPE_TO_LEGACY_IMAGE_TYPE: dict[str, str] = {
    "decision_tree": "decision_tree",
    "transformer": "mechanism_diagram",
    "rag": "system_architecture",
    "swot": "comparison_matrix",
    "attention_matrix": "matrix_diagram",
    "process_flow": "process_flow",
    "chart": "data_visualization",
    "scene_illustration": "scene_illustration",
    "infographic": "infographic",
    "concept_illustration": "concept_diagram",
}


def resolve_renderer_key(diagram_subtype: str, *, has_numeric_data: bool = False) -> str:
    st = (diagram_subtype or "").strip().lower()
    if st == "chart" and not has_numeric_data:
        return RENDERER_NEED_DATA
    return SUBTYPE_TO_RENDERER.get(st, RENDERER_STRUCTURED_GENERIC)


def is_structured_renderer(renderer: str) -> bool:
    return (renderer or "") in STRUCTURED_RENDERERS or (renderer or "").startswith("structured.")
