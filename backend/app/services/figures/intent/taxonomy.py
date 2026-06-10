"""Diagram family / subtype 与 renderer 映射。

原则：分类只表达“画什么”，renderer 只表达“怎么画”。
书稿内页中，含结构/文字的图尽量走结构化渲染；只有真正的场景氛围图走 Image API。
"""

from __future__ import annotations

# Renderer 键（单一真相）
RENDERER_STRUCTURED_GENERIC = "structured.generic_graph"
RENDERER_STRUCTURED_TRANSFORMER = "structured.transformer"
RENDERER_STRUCTURED_RAG = "structured.rag"
RENDERER_STRUCTURED_SWOT = "structured.swot"
RENDERER_STRUCTURED_MATRIX = "structured.matrix"
RENDERER_STRUCTURED_FLOWCHART = "structured.flowchart"
RENDERER_STRUCTURED_CHART = "structured.chart"
RENDERER_STRUCTURED_TIMELINE = "structured.timeline"
RENDERER_STRUCTURED_TAXONOMY = "structured.taxonomy"
RENDERER_STRUCTURED_COMPARISON = "structured.comparison"
RENDERER_STRUCTURED_ARCHITECTURE = "structured.architecture"
RENDERER_STRUCTURED_NETWORK = "structured.network"
RENDERER_STRUCTURED_INFOGRAPHIC = "structured.infographic"
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
    RENDERER_STRUCTURED_TIMELINE,
    RENDERER_STRUCTURED_TAXONOMY,
    RENDERER_STRUCTURED_COMPARISON,
    RENDERER_STRUCTURED_ARCHITECTURE,
    RENDERER_STRUCTURED_NETWORK,
    RENDERER_STRUCTURED_INFOGRAPHIC,
})

# V2 recommended subtype set. Keep old aliases below for compatibility.
STRUCTURAL_SUBTYPES = frozenset({
    "concept_diagram",
    "mechanism_diagram",
    "process_flow",
    "system_architecture",
    "comparison_matrix",
    "taxonomy_map",
    "timeline_roadmap",
    "decision_tree",
    "infographic",
    "mindmap",
    "knowledge_graph",
    "org_chart",
    "hierarchy_chart",
})

SUBTYPE_TO_RENDERER: dict[str, str] = {
    # generic structured book diagrams
    "concept_diagram": RENDERER_STRUCTURED_GENERIC,
    "mechanism_diagram": RENDERER_STRUCTURED_GENERIC,
    "process_flow": RENDERER_STRUCTURED_GENERIC,
    "business_workflow": RENDERER_STRUCTURED_GENERIC,
    "system_architecture": RENDERER_STRUCTURED_ARCHITECTURE,
    "microservice_architecture": RENDERER_STRUCTURED_ARCHITECTURE,
    "comparison_matrix": RENDERER_STRUCTURED_COMPARISON,
    "quadrant_matrix": RENDERER_STRUCTURED_SWOT,
    "taxonomy_map": RENDERER_STRUCTURED_TAXONOMY,
    "mindmap": RENDERER_STRUCTURED_TAXONOMY,
    "knowledge_graph": RENDERER_STRUCTURED_NETWORK,
    "timeline_roadmap": RENDERER_STRUCTURED_TIMELINE,
    "timeline": RENDERER_STRUCTURED_TIMELINE,
    "roadmap": RENDERER_STRUCTURED_TIMELINE,
    "org_chart": RENDERER_STRUCTURED_TAXONOMY,
    "hierarchy_chart": RENDERER_STRUCTURED_TAXONOMY,
    "decision_tree": RENDERER_STRUCTURED_GENERIC,
    "decision_flow": RENDERER_STRUCTURED_GENERIC,
    "infographic": RENDERER_STRUCTURED_INFOGRAPHIC,
    "chapter_summary": RENDERER_STRUCTURED_INFOGRAPHIC,
    # specialized structured diagrams
    "transformer": RENDERER_STRUCTURED_TRANSFORMER,
    "rag": RENDERER_STRUCTURED_ARCHITECTURE,
    "agent": RENDERER_STRUCTURED_ARCHITECTURE,
    "swot": RENDERER_STRUCTURED_SWOT,
    "attention_matrix": RENDERER_STRUCTURED_MATRIX,
    "chart": RENDERER_STRUCTURED_CHART,
    # illustration only when the purpose is atmosphere / concrete scene
    "scene_illustration": RENDERER_ILLUSTRATION,
    "case_scene": RENDERER_ILLUSTRATION,
    "future_scene": RENDERER_ILLUSTRATION,
    "human_ai_scene": RENDERER_ILLUSTRATION,
    # legacy alias: do not send concept to image API anymore
    "concept_illustration": RENDERER_STRUCTURED_GENERIC,
}

FAMILY_DEFAULT_SUBTYPE: dict[str, str] = {
    "architecture": "system_architecture",
    "decision": "decision_tree",
    "workflow": "process_flow",
    "matrix": "comparison_matrix",
    "knowledge": "concept_diagram",
    "timeline": "timeline_roadmap",
    "organization": "org_chart",
    "illustration": "scene_illustration",
    "data": "chart",
}

# 兼容旧 image_type 字段
SUBTYPE_TO_LEGACY_IMAGE_TYPE: dict[str, str] = {
    "concept_diagram": "concept_diagram",
    "concept_illustration": "concept_diagram",
    "mechanism_diagram": "mechanism_diagram",
    "transformer": "mechanism_diagram",
    "rag": "system_architecture",
    "agent": "system_architecture",
    "system_architecture": "system_architecture",
    "process_flow": "process_flow",
    "business_workflow": "process_flow",
    "decision_tree": "decision_tree",
    "swot": "comparison_matrix",
    "comparison_matrix": "comparison_matrix",
    "quadrant_matrix": "comparison_matrix",
    "attention_matrix": "matrix_diagram",
    "taxonomy_map": "taxonomy_map",
    "mindmap": "taxonomy_map",
    "knowledge_graph": "taxonomy_map",
    "timeline": "timeline_roadmap",
    "roadmap": "timeline_roadmap",
    "timeline_roadmap": "timeline_roadmap",
    "chart": "data_visualization",
    "scene_illustration": "scene_illustration",
    "case_scene": "scene_illustration",
    "future_scene": "scene_illustration",
    "human_ai_scene": "scene_illustration",
    "infographic": "infographic",
    "chapter_summary": "infographic",
    "org_chart": "taxonomy_map",
    "hierarchy_chart": "taxonomy_map",
}


# 文档 diagram_type ↔ 内部 diagram_subtype 双向映射
DIAGRAM_TYPE_TO_SUBTYPE: dict[str, str] = {
    "flowchart": "process_flow",
    "decision_flow": "decision_tree",
    "architecture": "system_architecture",
    "dataflow": "process_flow",
    "sequence": "process_flow",
    "hierarchy": "org_chart",
    "taxonomy": "taxonomy_map",
    "comparison": "comparison_matrix",
    "matrix": "swot",
    "timeline": "timeline_roadmap",
    "illustration": "scene_illustration",
    "chart": "chart",
    "data": "chart",
}

SUBTYPE_TO_DIAGRAM_TYPE: dict[str, str] = {
    "process_flow": "flowchart",
    "business_workflow": "flowchart",
    "decision_tree": "decision_flow",
    "decision_flow": "decision_flow",
    "system_architecture": "architecture",
    "microservice_architecture": "architecture",
    "rag": "architecture",
    "agent": "architecture",
    "transformer": "architecture",
    "taxonomy_map": "taxonomy",
    "mindmap": "taxonomy",
    "knowledge_graph": "taxonomy",
    "org_chart": "hierarchy",
    "hierarchy_chart": "hierarchy",
    "comparison_matrix": "comparison",
    "swot": "matrix",
    "quadrant_matrix": "matrix",
    "attention_matrix": "matrix",
    "timeline_roadmap": "timeline",
    "timeline": "timeline",
    "roadmap": "timeline",
    "infographic": "taxonomy",
    "concept_diagram": "taxonomy",
    "mechanism_diagram": "flowchart",
    "chart": "chart",
    "scene_illustration": "illustration",
    "case_scene": "illustration",
    "future_scene": "illustration",
    "human_ai_scene": "illustration",
}


def diagram_type_to_subtype(diagram_type: str) -> str:
    dt = (diagram_type or "").strip().lower()
    return DIAGRAM_TYPE_TO_SUBTYPE.get(dt, canonical_subtype(dt))


def subtype_to_diagram_type(diagram_subtype: str) -> str:
    st = canonical_subtype(diagram_subtype)
    return SUBTYPE_TO_DIAGRAM_TYPE.get(st, "flowchart")


def canonical_subtype(diagram_subtype: str) -> str:
    """遗留/别名 subtype → 规范主类型（见 catalog/type_catalog.py）。"""
    st = (diagram_subtype or "").strip().lower()
    aliases = {
        # 形式别名
        "architecture": "system_architecture",
        "flowchart": "process_flow",
        "workflow": "process_flow",
        "business_workflow": "process_flow",
        "dataflow": "process_flow",
        "sequence": "process_flow",
        "pipeline": "process_flow",
        "taxonomy": "taxonomy_map",
        "mindmap": "taxonomy_map",
        "mind_map": "taxonomy_map",
        "org_chart": "taxonomy_map",
        "hierarchy": "taxonomy_map",
        "hierarchy_chart": "taxonomy_map",
        "timeline": "timeline_roadmap",
        "roadmap": "timeline_roadmap",
        "timeline_map": "timeline_roadmap",
        "concept": "concept_diagram",
        "illustration": "scene_illustration",
        "case_scene": "scene_illustration",
        "future_scene": "scene_illustration",
        "human_ai_scene": "scene_illustration",
        "summary": "infographic",
        "chapter_summary": "infographic",
        "decision_flow": "decision_tree",
        "comparison": "comparison_matrix",
        "quadrant_matrix": "swot",
        "data_visualization": "chart",
        # 领域词归并（非独立类型）
        "rag": "system_architecture",
        "agent": "system_architecture",
        "microservice_architecture": "system_architecture",
        "transformer": "mechanism_diagram",
    }
    if st in aliases:
        return aliases[st]
    if st == "matrix":
        return "swot"
    return st or "concept_diagram"


def resolve_renderer_key(diagram_subtype: str, *, has_numeric_data: bool = False) -> str:
    raw = (diagram_subtype or "").strip().lower()
    if raw == "chart" and not has_numeric_data:
        return RENDERER_NEED_DATA
    if raw in SUBTYPE_TO_RENDERER:
        return SUBTYPE_TO_RENDERER[raw]
    st = canonical_subtype(diagram_subtype)
    if st == "chart" and not has_numeric_data:
        return RENDERER_NEED_DATA
    return SUBTYPE_TO_RENDERER.get(st, RENDERER_STRUCTURED_GENERIC)


def is_structured_renderer(renderer: str) -> bool:
    return (renderer or "") in STRUCTURED_RENDERERS or (renderer or "").startswith("structured.")
